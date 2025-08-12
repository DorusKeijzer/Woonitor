import json
import logging
import os
import psycopg
import re
import redis
import uuid

from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from psycopg import sql
from psycopg.types.json import Json
from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway
from time import time
from typing import Dict, Tuple, Optional, Any

from config import BATCH_SIZE, FLUSH_TIME_LIMIT

load_dotenv()

# logging 
logging.basicConfig(
    level=logging.INFO,  
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# redis connection
r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    password=os.getenv("REDIS_PASSWORD") or None
)

# postgres connection
print("Connecting to postgres")
try: 
    conn = psycopg.connect(f"host={os.getenv("POSTGRES_HOST")} \
                    connect_timeout=10 \
                    dbname={os.getenv("POSTGRES_DB")}\
                    user={os.getenv("POSTGRES_USER")}\
                    password={os.getenv("POSTGRES_PASSWORD")}")
    print("connection: ", conn)

except psycopg.OperationalError as e:
    print("connection failed")
    raise e 

# prometheus stuff
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "localhost:9091")
job_name = "Writer"
registry = CollectorRegistry()

class Writer:
    def __init__(self):
        self.name= f"Writer-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initialized writer {self.name}.")
        self.conn = conn
        self.writes = Counter('writer_writes', 'Number of succesful writes by writers', ["writes"], registry=registry)

    def listen(self):
        batch = []
        last_flush = time()

        while True:
            try:
                self.logger.info("Fetching item from queue...")
                item = r.brpop('data_queue', timeout=5)
                if item:
                    _, raw = item
                    message = json.loads(raw.decode())
                    if self.validate_input(message):
                        self.logger.info("Input valid. Transforming message...")

                        transformed = self.transform(message)

                        if self.validate_output(transformed):
                            self.logger.info("Output valid")
                            batch.append(transformed)
                        else:
                            self.logger.info("Output invalid")
                    else:
                        self.logger.info("Input invalid, moving on to next item.")
            except Exception as e:
                self.logger.error(f"Queue read or transform failed: {e}")

            # Flush if batch is large enough or time passed
            if len(batch) >= BATCH_SIZE or (time() - last_flush) > FLUSH_TIME_LIMIT:
                if batch:
                    self.write(batch)
                    batch = []
                    last_flush = time()


    def write(self, listings: list[dict]):
        if not listings:
            return

        columns = list(listings[0].keys())

        # Wrap misc_data in Json 
        values = []
        for listing in listings:
            row = []
            for col in columns:
                value = listing[col]
                if col == "misc_data" and isinstance(value, dict):
                    row.append(Json(value))
                else:
                    row.append(value)
            values.append(row)

        placeholders = sql.SQL(', ').join(sql.Placeholder() * len(columns))

        insert_query = sql.SQL("""
            INSERT INTO listings ({fields})
            VALUES ({placeholders})
            ON CONFLICT (funda_id)
            DO NOTHING
        """).format(
            fields=sql.SQL(', ').join(map(sql.Identifier, columns)),
            placeholders=placeholders
        )

        try:
            with self.conn.cursor() as cur:
                cur.executemany(insert_query, values)
            self.conn.commit()
            self.logger.info(f"Wrote batch of {len(listings)} listings to database")
            self.writes.labels(code='success').inc()
        except Exception as e:
            self.logger.error(f"Failed to write batch: {e}")
            self.writes.labels(code='failure').inc()
            self.conn.rollback()


    def reduce_to_int(self, string: str) -> int:
        """Reduce a string to just the numbers in the string and store as integer."""
        return int("".join([element for element in string if element in "0123456789"]))

    def parse_rooms(self, text: str) -> Tuple[int, Optional[int]]:
        """
        Extract total number of rooms and bedrooms from a Dutch real estate listing string.

        Parameters:
            text (str): e.g. "5 kamers (3 slaapkamers)" or "3 kamers"

        Returns:
            (total_rooms, bedrooms) — bedrooms is None if not specified
        """
        # Match total number of rooms
        total_match = re.search(r"(\d+)\s+kamers?", text)
        total_rooms = int(total_match.group(1)) if total_match else None

        # Match number of bedrooms (optionally singular)
        bedroom_match = re.search(r"\((\d+)\s+slaapkamers?\)", text)
        bedrooms = int(bedroom_match.group(1)) if bedroom_match else None

        return (total_rooms, bedrooms)

    def to_date(self, date_str: str) -> date:
        """Reduce string to a date"""
        months = {
            "januari": 1,
            "februari": 2,
            "maart": 3,
            "april": 4,
            "mei": 5,
            "juni": 6,
            "juli": 7,
            "augustus": 8,
            "september": 9,
            "oktober": 10,
            "november": 11,
            "december": 12,
        }

        parts = date_str.lower().split()
        if len(parts) != 3:
            raise ValueError(f"Invalid date format: {date_str}")

        day = int(parts[0])
        month = months.get(parts[1])
        year = int(parts[2])

        if not month:
            raise ValueError(f"Unknown Dutch month: {parts[1]}")

        return date(year, month, day)

    def split_postcode_city(self, postcode_str: str) -> Tuple[str, str]:
        """
        Splits a Dutch-style postcode and city string into postcode and city.

        Example:
            "5035 DD Tilburg" -> ("5035 DD", "Tilburg")

        Assumes input always has exactly 3 parts.
        """
        parts = postcode_str.strip().split()
        postcode = f"{parts[0]} {parts[1]}"
        city = parts[2]
        return postcode, city

    def validate_input(self, message) -> bool:
        required_fields = ["funda_id", "url", "scraped_at", "Postcode"]
        missing = [f for f in required_fields if f not in message]

        if missing != []:
            return False

        for f in required_fields:
            if message.get(f) is None:
                return False


        return True


    def validate_output(self, transformed_message: dict) -> bool:
        """Ensures that the transformed information has the correct format"""

        required_fields = {
            "funda_id": str,
            "title": str,
            "last_asking_price": int,
            "surface_area": int,
            "total_rooms": int,
            "listing_type": str,
            "sell_date": date,
            "offer_since": date,
            "sell_duration": timedelta,
            "city": str,  # Only if you're including this
            "postcode": str,
            "neighborhood": str,
            "energy_label": str,
            "building_year": (date, type(None)),
            "scraped_at": datetime,
            "url": str,
            "misc_data": dict,
        }

        optional_fields = {
            "bedrooms": (int, type(None)),
        }

        # Check required fields
        for field, expected_type in required_fields.items():
            if field not in transformed_message:
                self.logger.info(f"Missing required field: {field}")
                return False
            if not isinstance(transformed_message[field], expected_type):
                self.logger.info(f"Invalid type for field '{field}': expected {expected_type}, got {type(transformed_message[field])}")
                return False

        # Check optional fields
        for field, expected_type in optional_fields.items():
            if field in transformed_message and not isinstance(transformed_message[field], expected_type):
                self.logger.info(f"Invalid type for optional field '{field}': expected {expected_type}, got {type(transformed_message[field])}")
                return False

        return True

                
    def transform(self, message: Dict[str, str]) -> Dict[str, str | int | date | Any]:
        """Transforms scraped listing data to fit the database schema."""
        result = {}

        # Keep passthrough fields
        result["funda_id"] = message["funda_id"]
        result["url"] = message["url"]
        result["scraped_at"] = message["scraped_at"]

        # Room parsing
        if "Aantal kamers" in message:
            total, bedrooms = self.parse_rooms(message["Aantal kamers"])
            result["total_rooms"] = total
            result["bedrooms"] = bedrooms

        postcode, city = self.split_postcode_city(message["Postcode"])

        result["postcode"] = postcode
        result["city"] = city

        # Field mapping: source -> target
        field_map = {
            "Titel": "title",
            "Laatste vraagprijs": "last_asking_price",
            "Gebruiksoppervlakten": "surface_area",
            "Soort appartement": "listing_type",
            "Soort woonhuis": "listing_type",
            "Verkoopdatum": "sell_date",
            "Aangeboden sinds": "offer_since",
            "Buurt": "neighborhood",
            "Energielabel": "energy_label",
            "Bouwjaar": "building_year"
        }

        for src, dst in field_map.items():
            if src not in message:
                continue
            value = message[src]
            if dst in ["last_asking_price", "surface_area"]:
                result[dst] = self.reduce_to_int(value)
            elif dst in ["sell_date", "offer_since"]:
                result[dst] = self.to_date(value)
            elif dst == "building_year":
                try:
                    result[dst] = date(int(value), 1, 1)
                except ValueError:
                    result[dst] = None  # fallback if bouwjaar is malformed
            else:
                result[dst] = value

        # Ensure building year exists (even though it might be none)
        if result.get("building_year") is None:
            result["building_year"] = None

        # Derived duration field
        if result.get("sell_date") and result.get("offer_since"):
            result["sell_duration"] = result["sell_date"] - result["offer_since"]

        # Add all remaining fields to misc_data
        # These fields are either used or inferred from other data
        used_keys = set(field_map.keys()) | {
            "Aantal kamers", "funda_id", "url", "scraped_at", "Postcode", "postcode", "Looptijd", "city"
        }

        # wrangle scraped_at into a datetime
        result["scraped_at"] = datetime.strptime(result["scraped_at"], "%Y-%m-%d %H:%M:%S")

        result["misc_data"] = {
            k: v for k, v in message.items() if k not in used_keys
        }

        return result

if __name__ == "__main__":
    writer = Writer()
    writer.listen()

import json
import logging
import os
import psycopg
import re
import redis
import uuid

from datetime import date, datetime
from dotenv import load_dotenv
from typing import Dict, Tuple, Optional, Any

from config import BATCH_SIZE

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
# postgres conncetion

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

class Writer:
    def __init__(self):
        self.name= f"Writer-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initialized writer {self.name}.")

    def listen(self):
        """Listens to the redis message queue, stores listing data in memory and writes to db occasionally"""
        batch = []

        while True:
            # _, raw = r.brpop('data_queue', timeout=5)
            raw = r.lrange('data_queue', 0, 0)[0]
            message = json.loads(raw.decode())
            transformed_message = self.transform(message)

            if self.validate(transformed_message):
                batch.append(transformed_message)    
            else:
                print(f"Message {transformed_message} did not pass validation step")

            if len(batch) >= BATCH_SIZE:
                self.write(batch)
                batch = []

    def reduce_to_int(self, string: str) -> int:
        """Reduce a string to just the numbers in the string and store as integer."""
        return int("".join([element for element in string if element.isdigit()]))

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

    def to_date(self, string: str) -> date:
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

    def validate(self, transformed_message: dict)-> bool:
        """Ensures that the transformed information has the correct format"""
        ...
                
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

        # Field mapping: source -> target
        field_map = {
            "Adres": "title",
            "Laatste vraagprijs": "last_asking_price",
            "Gebruiksoppervlakten": "surface_area",
            "Soort appartement": "listing_type",
            "Verkoopdatum": "sell_date",
            "Aangeboden sinds": "offer_since",
            "Postcode": "postcode",
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

        # Derived duration field
        if result.get("sell_date") and result.get("offer_since"):
            result["sell_duration"] = result["sell_date"] - result["offer_since"]

        # Add all remaining fields to misc_data
        used_keys = set(field_map.keys()) | {
            "Aantal kamers", "funda_id", "url", "scraped_at"
        }
        result["misc_data"] = {
            k: v for k, v in message.items() if k not in used_keys
        }

        return result



 #
# CREATE TABLE listings (
#     id SERIAL PRIMARY KEY,
#     funda_id TEXT UNIQUE NOT NULL,  -- Funda's listing ID
#     title TEXT,                     -- The title of the page on funda
#     last_asking_price INTEGER,      
#     surface_area NUMERIC,           -- Main surface area (?)
#     bedrooms INTEGER, 
#     total_rooms INTEGER, 
#     listing_type TEXT,              -- House, apartment, etc.
#     sell_date DATE,
#     offer_since DATE,               -- listed since
#     sell_duration INTERVAL,         -- time between offer date and sell date
#     city TEXT,  
#     postcode TEXT, 
#     neighborhood TEXT, 
#     energy_label TEXT,
#     building_year DATE,
#     scraped_at TIMESTAMP NOT NULL,
#     url TEXT,
#     misc_data JSONB                   -- Other data from the listing
# );

       



    def write(self, listings: list[dict]):
        ...


if __name__ == "__main__":
    writer = Writer()
    writer.listen()

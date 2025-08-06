import json
import logging
import os
import psycopg
import redis
import uuid

from dotenv import load_dotenv
from time import sleep

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
        """Listens to the redis message queue and stores listing data in memory"""
        while True:
            _, raw = r.brpop('listing_queue')
            message = json.loads(raw.decode())


    def write(self, listings):
        ...


if __name__ == "__main__":
    writer = Writer()
    writer.listen()

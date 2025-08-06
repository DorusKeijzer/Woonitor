import json
import logging
import os
import psycopg
import redis

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
    ... 

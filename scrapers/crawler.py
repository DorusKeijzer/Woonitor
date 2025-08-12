import json
import logging
import os
import psycopg
import redis
import uuid

from dotenv import load_dotenv
from parsel import Selector
from playwright.sync_api import sync_playwright
from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway
from random import random, choice
from sys import exit
from time import sleep

from config import CRAWLER_THROTTLE_SPEED_MAX, CRAWLER_THROTTLE_SPEED_MIN
load_dotenv()   

logging.basicConfig(
    level=logging.INFO,  
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    password=os.getenv("REDIS_PASSWORD") or None
)

dedup_push_script = r.register_script("""
    local set_key = KEYS[1]
    local list_key = KEYS[2]
    local url = ARGV[1]
    local payload = ARGV[2]

    if redis.call("SISMEMBER", set_key, url) == 0 then
        redis.call("SADD", set_key, url)
        redis.call("LPUSH", list_key, payload)
        return 1
    else
        return 0
    end
""")

# prometheus stuff
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "localhost:9091")
registry = CollectorRegistry()

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

cur = conn.cursor()


class Crawler:
    """Takes the name of an area and returns all available listings in the area"""
    def __init__(self, area: str):
        self.area = area
        self.cleaned_area = area.lower().replace(" ", "-")
        self.base_url = f"https://www.funda.nl/zoeken/koop/?selected_area=[\"{self.cleaned_area}\"]&availability=[\"unavailable\"]&search_result="
        self.name= f"Crawler-{area}-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initialized crawler {self.name}.")
        # prometheus information
        self.new_pages_found = Counter('crawler_new_pages_found_total', 'Number of new pages found', registry=registry)
        self.status_codes = Counter(
            'crawler_http_status_codes_total', 
            'Count of HTTP status codes', 
            ['code'], 
            registry=registry
        )
        self.captchas = Counter('crawler_captchas', 'Number of captchas served', registry=registry)

    def crawl_links(self):
        page_number = 1
        while True:

            self.logger.info(f"Crawling page {page_number}")
            url = self.base_url + str(page_number)

            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.5; rv:117.0) Gecko/20100101 Firefox/117.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ]
            ua = choice(user_agents)

            with sync_playwright() as p:
                self.logger.info(f"Making request to {url} with user agent {ua} ...")
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(user_agent=ua)
                page = context.new_page()
                response = page.goto(url)            
                if response:
                    self.logger.info(f"Response status: {response.status}")
                    if response.status == 200:
                        self.status_codes.labels(code='200').inc()
                    if response.status == 403:
                        self.status_codes.labels(code='403').inc()
                    if response.status == 429:
                        self.status_codes.labels(code='429').inc()

                    # if response.status in [403,429]:
                        # self.logger.info(f"Exiting because of encountering status code {response.status}")
                        # exit(1)
                else:
                    self.logger.info(f"Response is empty")
                # wait for the page to load
                page.wait_for_load_state("networkidle")
                content = page.content()
                selector = Selector(text = content)
                
                title = selector.css("title::text").get()
                self.logger.info(f"Page title: {title}")

                # Funda serves a page titled "Je bent bijna op de pagina die je zoekt" 
                # and a captcha if it suspect bot activity
                if title and "Je bent bijna op de pagina die" in title:
                    self.logger.info("Encountered Captcha page")
                    self.captchas.inc(1)

                    # self.logger.info("Exiting because served captcha page")
                    # exit(1)
                
                

                # gets the listing urls from the ordered list
                urls = selector.css("div.flex.flex-col.gap-3.mt-4 a::attr(href)").getall()

                # filter only listing pages while ommitting duplicates
                urls = list(set([url for url in urls if url.startswith("/detail/")]))
                self.logger.info(urls)


                i = 0 
                for url in urls:
                    # filter if url already in postgres
                    cur.execute("SELECT 1 FROM listings WHERE url = %s LIMIT 1;", (urls,))
                    if cur.fetchone():
                        continue
                    
                    listing = {
                        "sender": self.name,
                        "url": url,
                        "area": self.cleaned_area
                    }
                    pushed = dedup_push_script(
                        keys=["listing_seen", "listing_queue"],
                        args=[url, json.dumps(listing)]
                    )

                    # only push if no duplicate in redis or postgres
                    if pushed == 1:
                        self.new_pages_found.inc()
                        i += 1
                
                push_to_gateway(PUSHGATEWAY_URL, 
                                job=self.name, 
                                # instance= self.name, 
                                registry=registry)


                self.logger.info(f"Succesfully pushed {i} urls.")
                
                browser.close()

            page_number += 1
            sleeptime = random() * (CRAWLER_THROTTLE_SPEED_MAX - CRAWLER_THROTTLE_SPEED_MIN) + CRAWLER_THROTTLE_SPEED_MIN

            self.logger.info(f"Sleeping {sleeptime} seconds.")
            sleep(sleeptime)

            if page_number > 64:
                self.logger.info(f"Quitting because page number is {page_number}")
                quit(0)





if __name__ == "__main__":
    crawler = Crawler("Tilburg")
    crawler.crawl_links()

    

import json
import logging
import os
import redis
import uuid

from dotenv import load_dotenv
from parsel import Selector
from playwright.sync_api import sync_playwright
from prometheus_client import CollectionRegistry, Gauge, Counter, push_to_gateway
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

# prometheus stuff
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "localhost:9091")
job_name = "Crawler"
registry = CollectionRegistry()

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
        self.new_pages_found = Counter('new_pages_found_total', 'Number of new pages found', registry=registry)
        self.status_200 = Counter('status_200', 'Number of 200 responses', registry=registry)
        self.status_403 = Counter('status_403', 'Number of 403 responses', registry=registry)
        self.status_429 = Counter('status_429', 'Number of 429 responses', registry=registry)
        self.captchas = Counter('captchas', 'Number of captchas served', registry=registry)

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
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=ua)
                page = context.new_page()
                response = page.goto(url)            
                if response:
                    self.logger.info(f"Response status: {response.status}")
                    if response.status == 200:
                        self.status_200.inc(1)
                    if response.status == 403:
                        self.status_403.inc(1)
                    if response.status == 429:
                        self.status_429.inc(1)

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
                print(type(title))

                # Funda serves a page titled "Je bent bijna op de pagina die je zoekt" 
                # and a captcha if it suspect bot activity
                if title and "Je bent bijna op de pagina die" in title:
                    self.captchas.inc(1)

                    # self.logger.info("Exiting because served captcha page")
                    # exit(1)
                
                

                # gets the listing urls from the ordered list
                urls = selector.css("div.flex.flex-col.gap-3.mt-4 a::attr(href)").getall()

                # filter only listing pages while ommitting duplicates
                urls = list(set([url for url in urls if url.startswith("/detail/")]))
                self.logger.info(urls)

                self.logger.info(f"Found {len(urls)} urls.")

                for url in urls:
                    listing = {
                        "sender": self.name,
                        "url": url,
                        "area":  self.cleaned_area
                    }
                    r.lpush("listing_queue", json.dumps(listing))

                self.new_pages_found.inc(len(urls))
                push_to_gateway(PUSHGATEWAY_URL, job=job_name, instance= self.name, registry=registry)

                browser.close()

            page_number += 1
            sleeptime = random() * (CRAWLER_THROTTLE_SPEED_MAX - CRAWLER_THROTTLE_SPEED_MIN) + CRAWLER_THROTTLE_SPEED_MIN

            self.logger.info(f"Sleeping {sleeptime} seconds.")
            sleep(sleeptime)

            if page_number == 5:
                break


if __name__ == "__main__":
    crawler = Crawler("Gemeente Utrecht")
    crawler.crawl_links()

    

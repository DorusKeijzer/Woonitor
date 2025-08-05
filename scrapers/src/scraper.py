from playwright.sync_api import sync_playwright
from parsel import Selector
from time import sleep
import uuid
import logging
from config import CRAWLER_THROTTLE_SPEED
import redis
import os
import json

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

class Crawler:
    """Listens to the redis queue and scrapes information of every listing it receives"""
    def __init__(self):
        self.name= f"Crawler-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initialized scraper {self.name}.")

    def scrape(self):
        page_number = 1

        while True:
            self.logger.info(f"Crawling page {page_number}")
            url = self.base_url + str(page_number)

            with sync_playwright() as p:
                self.logger.info(f"Making request to {url} ...")
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(url)            
                # wait for the page to load
                page.wait_for_load_state("networkidle")
                content = page.content()
                selector = Selector(text = content)

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
                    r.rpush("listing_queue", json.dumps(listing))

                browser.close()

            page_number += 1
            self.logger.info(f"Sleeping {CRAWLER_THROTTLE_SPEED} seconds.")
            sleep(CRAWLER_THROTTLE_SPEED)
            if page_number == 5:
                break


if __name__ == "__main__":
    scraper = Scraper("Gemeente Tilburg")
    scraper.scrape_links()

    for l in scraper.links:
        print(l)
    

from playwright.sync_api import sync_playwright
from parsel import Selector
from time import sleep
import uuid
import logging
from config import CRAWLER_THROTTLE_SPEED
import redis
import os
import json
from dotenv import load_dotenv
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

class Crawler:
    """Takes the name of an area and returns all available listings in the area"""
    def __init__(self, area: str):
        self.area = area
        self.cleaned_area = area.lower().replace(" ", "-")
        self.base_url = f"https://www.funda.nl/zoeken/koop/?selected_area=[\"{self.cleaned_area}\"]&availability=[\"unavailable\"]&search_result="
        self.name= f"Crawler-{area}-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initialized crawler {self.name}.")

    def crawl_links(self):
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
    crawler = Crawler("Gemeente Tilburg")
    crawler.crawl_links()

    for l in crawler.links:
        print(l)
    

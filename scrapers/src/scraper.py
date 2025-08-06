import json
import logging
import os
import psycopg
import redis
import uuid

from datetime import datetime
from dotenv import load_dotenv
from parsel import Selector
from playwright.sync_api import sync_playwright
from time import sleep

from config import SCRAPER_THROTTLE_SPEED

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

class Scraper:
    """Listens to the redis queue and scrapes information of every listing it receives"""
    def __init__(self):
        self.name= f"Scraper-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initialized scraper {self.name}.")

    def listen(self):
        """Listens to the redis message queue and scrapes the listings it receives"""
        while True:
            _, raw = r.brpop('listing_queue')
            url = json.loads(raw.decode()).get("url")
            self.logger.info(f"Got URL: {url}")
            self.scrape(url)
            sleep(SCRAPER_THROTTLE_SPEED)
            
    def scrape(self, url):
        """Scrapes all available data of the given listing and writes to the database"""
        url = "https://www.funda.nl" + url

        # take the penultimate part of the url when split at /
        # e.g. .../tilburg/appartement-de-fabrikant-type-c1-bouwnr-28/43859373/' -> [... 'tilburg', 'appartement-de-fabrikant-type-c1-bouwnr-28', '43859373', '']
        funda_id = url.split("/")[-2] 

        info = {"funda_id" : funda_id, "url": url, "scraped_at" : datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

        self.logger.info(f"Scraping page {url}")

        with sync_playwright() as p:
            self.logger.info(f"Making request to {url} ...")
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url)            

            # wait for the page to load
            page.wait_for_load_state("networkidle")
            content = page.content()
            selector = Selector(text = content)

            # --- about box --- #
            # Contains: address, postal code, neighborhood
            about_box = selector.css("div#about")

            info["Titel"] = about_box.css("h1 span::text").get() 
            info["Postcode"] = about_box.css("span.text-neutral-40::text").get()
            info["Buurt"] = about_box.css("a.ml-2.text-secondary-70::text").get()

            # --- purchase history --- #
            # contains: offered since, purchase date, duration
            purchase_history = selector.css("section.mt-6.border-b.border-neutral-20 dl div").getall()
            for element in purchase_history:
                key = Selector(element).css("dt::text").get()
                value = Selector(element).css("dd::text").get()
                info[key] = value

            # --- features --- #
            # contains: most everything else
            features = selector.css("section#features div dl").getall()
            for element in features:
                key = Selector(element).css("dt::text").get()
                value = Selector(element).css("dd span::text").get()
                info[key] = value

            for key in info.keys():
                print(f"{key}: {info[key]}")

            browser.close()
            r.lpush("data_queue", json.dumps(info))

            # sleep for a while
            self.logger.info(f"Sleeping {SCRAPER_THROTTLE_SPEED} seconds.")
            sleep(SCRAPER_THROTTLE_SPEED)



if __name__ == "__main__":
    scraper = Scraper()
    scraper.listen()
    # scraper.scrape("/detail/koop/tilburg/appartement-langestraat-6-02/43938990/")
    

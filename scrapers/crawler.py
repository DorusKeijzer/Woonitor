from playwright.sync_api import sync_playwright
from parsel import Selector
import uuid
import logging

logging.basicConfig(
    level=logging.INFO,  
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class Scraper:
    """Takes the name of an area and returns all available listings in the area"""
    def __init__(self, area: str):
        self.area = area
        self.base_url = f"https://www.funda.nl/zoeken/koop/?selected_area=[\"{area.lower()}\"]&search_result="
        self.links = []
        self.name= f"Scraper-{area}-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info("Initialized.")

    def scrape_links(self):
        page_number = 1

        while True:
            self.logger.info(f"Crawling page {page_number}")
            url = self.base_url + str(page_number)

            with sync_playwright() as p:
                self.logger.info(f"Making request to {url}...")
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(url)            
                page.wait_for_load_state("networkidle")
                content = page.content()
                selector = Selector(text = content)
                urls = selector.css("a").getall()
                self.logger.info(f"Found {len(urls)} urls.")
                browser.close()

            page_number += 1
            quit()

if __name__ == "__main__":
    scraper = Scraper("Tilburg")
    scraper.scrape_links()

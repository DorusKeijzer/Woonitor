

from playwright.sync_api import sync_playwright
from parsel import Selector

class Scraper:
    """Takes an individual listing and scrapes the available data from it"""
    def __init__(self):
        pass

    def scrape(self, url):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url)            
            page.wait_for_load_state("networkidle")
            content = page.content()
            selector = Selector(text = content)
            title = selector.css("title").get()
            print(title)
            browser.close()


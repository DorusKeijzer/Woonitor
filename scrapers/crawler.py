import json
import logging
import os
import redis
import uuid

from dotenv import load_dotenv
from parsel import Selector
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway
from random import random, choice
from time import sleep

from config import (
    CRAWLER_THROTTLE_SPEED_MAX,
    CRAWLER_THROTTLE_SPEED_MIN,
    CRAWLER_MAX_PAGES,
    CRAWLER_AREAS,
    CRAWLER_BASE_BACKOFF,
    CRAWLER_MAX_BACKOFF,
    CRAWLER_MAX_CONSECUTIVE_BLOCKS,
    PLAYWRIGHT_HEADLESS,
)
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

# NOTE: the crawler used to also open a Postgres connection to skip URLs already
# present in `listings`, but that check was buggy (compared against the whole
# `urls` list instead of a single url) and redundant: the Redis `listing_seen`
# set below already dedups within a run, and the writer's `ON CONFLICT
# (funda_id) DO NOTHING` dedups at the database level. The crawler stays
# stateless with respect to Postgres.


class Crawler:
    """Takes the name of an area and returns all available listings in the area"""
    def __init__(self, area: str):
        self.area = area
        self.cleaned_area = area.lower().replace(" ", "-")
        self.base_url = f'https://www.funda.nl/zoeken/koop/?selected_area=["{self.cleaned_area}"]&availability=["unavailable"]&search_result='

        self.name = f"Crawler-{area}-{uuid.uuid4().hex[:6]}"
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
        self.storing = Counter('crawler_storing', 'Number of storingen served', registry=registry)

    def crawl_links(self):
        page_number = 1
        consecutive_blocks = 0
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

            blocked = False
            crawl_failed = False
            i = 0
            with sync_playwright() as p:
                self.logger.info(f"Making request to {url} with user agent {ua} ...")
                browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
                try:
                    context = browser.new_context(user_agent=ua)
                    page = context.new_page()
                    response = page.goto(url)
                    if response:
                        self.logger.info(f"Response status: {response.status}")
                        if response.status == 200:
                            self.status_codes.labels(code='200').inc()
                        if response.status == 403:
                            self.status_codes.labels(code='403').inc()
                            blocked = True
                        if response.status == 429:
                            self.status_codes.labels(code='429').inc()
                            blocked = True
                    else:
                        self.logger.info(f"Response is empty")

                    if not blocked:
                        # Funda sometimes serves the page slowly enough (ads,
                        # trackers) that it never truly goes network-idle; a
                        # hard failure here used to crash the whole crawler,
                        # so fall back to whatever DOM is available instead.
                        try:
                            page.wait_for_load_state("networkidle")
                        except PlaywrightTimeoutError:
                            self.logger.warning("networkidle wait timed out, continuing with partial page")

                        content = page.content()
                        selector = Selector(text=content)

                        title = selector.css("title::text").get()
                        self.logger.info(f"Page title: {title}")

                        # Funda also blocks with HTTP 200 by serving a captcha
                        # page (titled "Je bent bijna op de pagina die je
                        # zoekt") or, on outages, a "Storing" page. Either way
                        # there's nothing to parse, so treat it the same as a
                        # 403/429: back off and retry.
                        if title and "Je bent bijna op de pagina die" in title:
                            self.logger.info("Encountered Captcha page")
                            self.captchas.inc(1)
                            blocked = True
                        elif title and "Storing" in title:
                            self.logger.info("Encountered storing page")
                            self.storing.inc(1)
                            blocked = True

                    if not blocked:
                        # gets the listing urls from the ordered list
                        urls = selector.css("div.flex.flex-col.gap-3.mt-4 a::attr(href)").getall()

                        # filter only listing pages while ommitting duplicates
                        urls = list(set([u for u in urls if u.startswith("/detail/")]))
                        self.logger.info(urls)

                        for listing_url in urls:
                            # Dedup is handled entirely by the Lua script (a
                            # Redis set) and, downstream, the writer's
                            # ON CONFLICT (funda_id); the crawler itself stays
                            # stateless w.r.t. Postgres.
                            listing = {
                                "sender": self.name,
                                "url": listing_url,
                                "area": self.cleaned_area
                            }
                            pushed = dedup_push_script(
                                keys=["listing_seen", "listing_queue"],
                                args=[listing_url, json.dumps(listing)]
                            )

                            if pushed == 1:
                                self.new_pages_found.inc()
                                i += 1

                        self.logger.info(f"Succesfully pushed {i} urls.")
                except Exception as e:
                    # A crashed page/browser must not take the whole crawler
                    # down (this used to happen on any Playwright timeout);
                    # treat it like a block and retry the same page.
                    self.logger.error(f"Failed to crawl page {page_number}: {e}")
                    crawl_failed = True
                finally:
                    browser.close()

                push_to_gateway(PUSHGATEWAY_URL, job="crawler",
                                 grouping_key={"instance": self.name}, registry=registry)

            if blocked or crawl_failed:
                consecutive_blocks += 1
                if consecutive_blocks > CRAWLER_MAX_CONSECUTIVE_BLOCKS:
                    self.logger.error(
                        f"Gave up after {consecutive_blocks} consecutive blocks/failures on page {page_number}"
                    )
                    return
                backoff = min(CRAWLER_MAX_BACKOFF, CRAWLER_BASE_BACKOFF * 2 ** (consecutive_blocks - 1))
                self.logger.warning(f"Blocked or failed, backing off {backoff}s before retrying page {page_number}")
                sleep(backoff)
                continue  # retry the same page_number

            consecutive_blocks = 0
            page_number += 1
            sleeptime = random() * (CRAWLER_THROTTLE_SPEED_MAX - CRAWLER_THROTTLE_SPEED_MIN) + CRAWLER_THROTTLE_SPEED_MIN

            self.logger.info(f"Sleeping {sleeptime} seconds.")
            sleep(sleeptime)

            if page_number > CRAWLER_MAX_PAGES:
                self.logger.info(f"Quitting because page number is {page_number}")
                return





if __name__ == "__main__":
    # Restores multi-city crawling: previously the base_url was hardcoded to
    # search all cities at once regardless of what area was passed in, which
    # both mislabelled every listing's `area` field and made per-city control
    # impossible. Now each city gets its own paginated crawl, one after another.
    for area in CRAWLER_AREAS:
        crawler = Crawler(area)
        crawler.crawl_links()

    

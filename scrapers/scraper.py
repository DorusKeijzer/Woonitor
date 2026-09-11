import json
import logging
import os
import redis
import uuid

from datetime import datetime
from dotenv import load_dotenv
from parsel import Selector
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway
from random import random, choice
from time import sleep

from config import (
    SCRAPER_THROTTLE_SPEED_MIN,
    SCRAPER_THROTTLE_SPEED_MAX,
    SCRAPER_BLOCKED_BACKOFF,
    SCRAPER_CONTENT_WAIT_MS,
    PLAYWRIGHT_HEADLESS,
    NODE_NAME,
)

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

# prometheus stuff
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "localhost:9091")
registry = CollectorRegistry()

class Scraper:
    """Listens to the redis queue and scrapes information of every listing it receives"""
    def __init__(self):
        self.name= f"Scraper-{uuid.uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initialized scraper {self.name}.")
        # Labeled by node (source machine) rather than just this process's
        # random instance name, so Grafana can graph contribution per source
        # machine across restarts (sum by (node) (...)) instead of per
        # process instance name, which changes every restart.
        self.pages_scraped = Counter(
            'scraper_pages_scraped', 'Number of pages scraped', ['node'], registry=registry
        )
        self.status_codes = Counter(
            'scraper_http_status_codes_total',
            'Count of HTTP status codes',
            ['code', 'node'],
            registry=registry
        )
        self.captchas = Counter(
            'scraper_captchas', 'Number of captchas served', ['node'], registry=registry
        )
        self._playwright = None
        self._browser = None

    def listen(self):
        """Listens to the redis message queue and scrapes the listings it receives"""
        # Launched once and reused across every listing instead of a fresh
        # Chromium process per request - that repeated cold-start was pure
        # overhead on top of the per-request throttle.
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        try:
            while True:
                _, raw = r.brpop('listing_queue')
                try:
                    url = json.loads(raw.decode()).get("url")
                    self.logger.info(f"Got URL: {url}")
                    self.scrape(url)
                except Exception as e:
                    # A single bad listing (parse error, crashed browser, ...) must
                    # not take the whole worker down. Keep the raw payload around
                    # for inspection instead of silently dropping it.
                    self.logger.error(f"Failed to scrape listing, moving to dead-letter queue: {e}")
                    r.lpush("listing_queue_dead", raw)
        finally:
            self._browser.close()
            self._playwright.stop()

    def scrape(self, relative_url):
        """Scrapes all available data of the given listing and writes to the database"""
        url = "https://www.funda.nl" + relative_url

        # take the penultimate part of the url when split at /
        # e.g. .../tilburg/appartement-de-fabrikant-type-c1-bouwnr-28/43859373/' -> [... 'tilburg', 'appartement-de-fabrikant-type-c1-bouwnr-28', '43859373', '']
        funda_id = url.split("/")[-2]

        info = {"funda_id" : funda_id, "url": url, "scraped_at" : datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


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

        self.logger.info(f"Scraping page {url} with user agent {ua}")

        context = self._browser.new_context(user_agent=ua)
        try:
            page = context.new_page()
            self.logger.info(f"Making request to {url} ...")
            response = page.goto(url)
            if response:
                self.logger.info(f"Response status: {response.status}")
                if response.status == 200:
                    self.status_codes.labels(code='200', node=NODE_NAME).inc()
                if response.status == 403:
                    self.status_codes.labels(code='403', node=NODE_NAME).inc()
                if response.status == 429:
                    self.status_codes.labels(code='429', node=NODE_NAME).inc()
            else:
                self.logger.info(f"Response is empty")

            # Wait for the actual listing content instead of full networkidle,
            # which Funda's ads/trackers mean rarely resolves within any
            # reasonable timeout. A captcha/storing page never has div#about,
            # so this just times out quickly there and falls through to the
            # title check below, which handles it.
            try:
                page.wait_for_selector("div#about", timeout=SCRAPER_CONTENT_WAIT_MS)
            except PlaywrightTimeoutError:
                self.logger.warning("Timed out waiting for listing content, checking page as-is")
            content = page.content()
            selector = Selector(text = content)

            title = selector.css("title::text").get()
            self.logger.info(f"Page title: {title}")

            # Funda serves a page titled "Je bent bijna op de pagina die je zoekt"
            # and a captcha if it suspects bot activity, and a "Storing" page on
            # outages. Either way there's no listing data on the page, so treat
            # it as a transient failure: requeue the URL for a later retry
            # instead of writing a near-empty row to data_queue.
            blocked = bool(title) and (
                "Je bent bijna op de pagina die" in title or "Storing" in title
            )
            if blocked:
                if "Je bent bijna op de pagina die" in title:
                    self.logger.warning("Encountered captcha page, requeueing for retry")
                    self.captchas.labels(node=NODE_NAME).inc()
                else:
                    self.logger.warning("Encountered storing page, requeueing for retry")
                r.lpush("listing_queue", json.dumps({"url": relative_url}))
                self._push_metrics()
                sleep(SCRAPER_BLOCKED_BACKOFF)
                return

            # --- about box --- #
            # Contains: address, postal code, neighborhood
            about_box = selector.css("div#about")

            info["Titel"] = about_box.css("h1 span::text").get()
            info["Postcode"] = about_box.css("span.text-neutral-40::text").get()
            info["Buurt"] = about_box.css("a.ml-2.text-secondary-70::text").get()

            # --- purchase history --- #
            # contains: offered since, purchase date, duration
            purchase_history = selector.css("section.mt-6.border-b.border-neutral-20 dl div")
            for element in purchase_history:
                key, value = self._extract_row(element)
                if key:
                    info[key] = value

            # --- features --- #
            # contains: most everything else.
            # NOTE: this used to select "section#features div dl" (the whole
            # <dl> per kenmerken subsection) and grab just its first dt/dd via
            # .get(). Unlike purchase_history above, this section's <dt>/<dd>
            # pairs are bare alternating siblings inside each <dl> - no
            # wrapping <div> - so every row after the first one in each
            # subsection was silently dropped. Most Kenmerken fields (plot
            # size, volume, insulation, heating, garden details, ...) never
            # actually reached misc_data before this fix.
            for dl in selector.css("section#features dl"):
                dts = dl.css("dt")
                dds = dl.css("dd")
                for dt, dd in zip(dts, dds):
                    key = "".join(dt.css("::text").getall()).strip()
                    value = "".join(dd.css("::text").getall()).strip()
                    if key:
                        info[key] = value

            # --- description --- #
            # The visible text is CSS-clamped behind a "read more" toggle, but
            # the full paragraph is already present in the DOM either way.
            description_section = selector.css("section.whitespace-pre-wrap")
            if description_section:
                heading = description_section.css("h2::text").get() or ""
                raw_text = " ".join(
                    t.strip() for t in description_section.css("*::text").getall() if t.strip()
                )
                description = raw_text[len(heading):].strip() if raw_text.startswith(heading) else raw_text
                for boilerplate in ("Lees de volledige omschrijving", "Toon minder"):
                    description = description.replace(boilerplate, "").strip()
                if description:
                    info["Omschrijving"] = description

            self.logger.debug(f"Scraped fields: {list(info.keys())}")

            self.pages_scraped.labels(node=NODE_NAME).inc()
            r.lpush("data_queue", json.dumps(info))
            self._push_metrics()

            # sleep for a while
            sleeptime = random() * (SCRAPER_THROTTLE_SPEED_MAX - SCRAPER_THROTTLE_SPEED_MIN) + SCRAPER_THROTTLE_SPEED_MIN
            self.logger.info(f"Sleeping {sleeptime} seconds.")
            sleep(sleeptime)
        finally:
            context.close()

    def _extract_row(self, element):
        """Extracts a (key, value) pair from a Funda dt/dd row.

        Uses "::text" (all descendant text) rather than "dt::text"/"dd::text"
        (direct text only) or "dd span::text" (requires a nested span) - not
        every row wraps its value in a span, and using the stricter selectors
        silently returned None for those.
        """
        key = "".join(element.css("dt ::text").getall()).strip()
        value = "".join(element.css("dd ::text").getall()).strip()
        return key, value

    def _push_metrics(self):
        try:
            push_to_gateway(PUSHGATEWAY_URL, job="scraper",
                             grouping_key={"instance": self.name}, registry=registry)
        except Exception as e:
            self.logger.info(f"failed to push metrics {e}")


if __name__ == "__main__":
    scraper = Scraper()
    scraper.listen()
    # scraper.scrape("/detail/koop/tilburg/appartement-langestraat-6-02/43938990/")
    

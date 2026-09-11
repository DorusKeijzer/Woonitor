import os

# --- BROWSER --- #
# Funda's anti-bot may fingerprint headless Chromium more aggressively than a
# headed one, which is why this used to be hardcoded to headless=False (running
# under Xvfb). Default to headless (faster, no Xvfb needed) but keep it a one-line
# env flip in case blocking gets worse: PLAYWRIGHT_HEADLESS=false in .env.
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").strip().lower() != "false"

# --- CRAWLER --- #
# Sleeping delay is picked uniformly between MIN and MAX:
CRAWLER_THROTTLE_SPEED_MIN = 5 #seconds
CRAWLER_THROTTLE_SPEED_MAX = 10 #seconds

# Funda caps search results at ~9990 listings / 166 pages of 60 results.
CRAWLER_MAX_PAGES = 166

# Cities the crawler cycles through in one run. Matches what the dashboard's
# geojsons and the writer's city filters already assume.
CRAWLER_AREAS = [
    "Tilburg",
    "Amsterdam",
    "Rotterdam",
    "Den Haag",
    "Utrecht",
    "Eindhoven",
    "Groningen",
]

# Backoff applied (in addition to the normal throttle) after a 403/429 response,
# doubling on consecutive blocks up to CRAWLER_MAX_BACKOFF, then giving up on that page.
CRAWLER_BASE_BACKOFF = 30 # seconds
CRAWLER_MAX_BACKOFF = 480 # seconds
CRAWLER_MAX_CONSECUTIVE_BLOCKS = 5

# Same idea as SCRAPER_CONTENT_WAIT_MS: wait for an actual listing link to
# show up instead of a full networkidle that rarely resolves.
CRAWLER_CONTENT_WAIT_MS = 10_000

# Funda sorts search results newest-first, so once a page yields zero URLs we
# haven't already seen, everything past it is old news too. After this many
# CONSECUTIVE all-already-seen pages, stop this city early instead of walking
# all CRAWLER_MAX_PAGES every run. Requires a few in a row (not just one) so a
# single freak empty page doesn't cut a run short.
CRAWLER_EARLY_STOP_EMPTY_PAGES = 3

# --- SCRAPER --- #
# Sleeping delay is picked uniformly between MIN and MAX:
SCRAPER_THROTTLE_SPEED_MIN = 2.5 #seconds
SCRAPER_THROTTLE_SPEED_MAX = 5 #seconds

# Backoff applied after a captcha/storing page before the URL is requeued.
SCRAPER_BLOCKED_BACKOFF = 30 # seconds

# How long to wait for the listing's actual content to show up before giving
# up and treating the page as loaded (used to detect captcha/storing pages).
# Much shorter than a full networkidle wait, which Funda's trackers/ads mean
# almost never actually resolves - this waits for a specific real signal
# instead of an idle network that may never come.
SCRAPER_CONTENT_WAIT_MS = 10_000

# --- WRITER --- #
# Writer will flush buffer at every BATCH_SIZE listings OR after FLUSH_TIME_LIMIT seconds
FLUSH_TIME_LIMIT = 20 # seconds
BATCH_SIZE = 10

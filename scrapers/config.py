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

# Backoff applied (in addition to the normal throttle) after a 403/429 response,
# doubling on consecutive blocks up to CRAWLER_MAX_BACKOFF, then giving up on that page.
CRAWLER_BASE_BACKOFF = 30 # seconds
CRAWLER_MAX_BACKOFF = 480 # seconds
CRAWLER_MAX_CONSECUTIVE_BLOCKS = 5

# --- SCRAPER --- #
# Sleeping delay is picked uniformly between MIN and MAX:
SCRAPER_THROTTLE_SPEED_MIN = 2.5 #seconds
SCRAPER_THROTTLE_SPEED_MAX = 5 #seconds

# Backoff applied after a captcha/storing page before the URL is requeued.
SCRAPER_BLOCKED_BACKOFF = 30 # seconds

# --- WRITER --- #
# Writer will flush buffer at every BATCH_SIZE listings OR after FLUSH_TIME_LIMIT seconds
FLUSH_TIME_LIMIT = 20 # seconds
BATCH_SIZE = 10

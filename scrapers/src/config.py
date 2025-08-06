# --- CRAWLER --- #
# Sleeping delay is picked uniformly between MIN and MAX:
CRAWLER_THROTTLE_SPEED_MIN = 5 #seconds
CRAWLER_THROTTLE_SPEED_MAX = 10 #seconds

# --- SCRAPER --- #
# Sleeping delay is picked uniformly between MIN and MAX:
SCRAPER_THROTTLE_SPEED_MIN = 5 #seconds
SCRAPER_THROTTLE_SPEED_MAX = 10 #seconds

# --- WRITER --- #
# Writer will flush buffer at every BATCH_SIZE listings OR after FLUSH_TIME_LIMIT seconds
FLUSH_TIME_LIMIT = 20 # seconds
BATCH_SIZE = 10 

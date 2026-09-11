import json
import logging
import os

import redis
from dotenv import load_dotenv
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from time import sleep

from config import CRAWLER_AREAS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("queue_metrics")

r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    password=os.getenv("REDIS_PASSWORD") or None
)

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "localhost:9091")
QUEUE_METRICS_INTERVAL = int(os.getenv("QUEUE_METRICS_INTERVAL", "30"))

# Both queues carry the crawler's {"area": ..., "url": ...} payload, so a
# city stuck retrying in the dead-letter queue shows up alongside its
# healthy backlog instead of only counting listing_queue.
CITY_QUEUES = ["listing_queue", "listing_queue_dead"]

# The crawler stores area as self.cleaned_area (area.lower().replace(" ", "-"),
# e.g. "Den Haag" -> "den-haag"), not the display name from CRAWLER_AREAS -
# normalize the same way so counts land on one key per city instead of
# splitting into a zeroed "Den Haag" and a populated "den-haag".
def _normalize(area):
    return area.lower().replace(" ", "-")


def count_by_city(queue_name):
    # Seed every known city at 0 so a city that has fully drained still
    # reports 0 instead of silently disappearing from the metric.
    counts = {_normalize(area): 0 for area in CRAWLER_AREAS}
    for raw in r.lrange(queue_name, 0, -1):
        try:
            area = json.loads(raw).get("area")
        except (json.JSONDecodeError, AttributeError):
            continue
        if area is None:
            continue
        counts[area] = counts.get(area, 0) + 1
    return counts


def main():
    logger.info(f"Starting queue metrics loop, polling every {QUEUE_METRICS_INTERVAL}s")
    while True:
        # Fresh registry/Gauge each push: pushgateway keeps whatever was
        # last pushed for a job forever, so this must re-push every city's
        # current count (including zeros) rather than only the ones with
        # a nonzero backlog this round.
        registry = CollectorRegistry()
        queue_size = Gauge(
            'redis_queue_city_size',
            'Number of items queued per city',
            ['queue', 'city'],
            registry=registry
        )

        for queue_name in CITY_QUEUES:
            try:
                counts = count_by_city(queue_name)
            except redis.RedisError as e:
                logger.error(f"Failed to read {queue_name}: {e}")
                continue
            for city, count in counts.items():
                queue_size.labels(queue=queue_name, city=city).set(count)
            logger.info(f"{queue_name}: {counts}")

        try:
            push_to_gateway(PUSHGATEWAY_URL, job="queue_metrics", registry=registry)
        except Exception as e:
            logger.error(f"Failed to push to pushgateway: {e}")

        sleep(QUEUE_METRICS_INTERVAL)


if __name__ == "__main__":
    main()

import asyncio

from arq.connections import RedisSettings

from async_worker.config import settings
from async_worker.tasks.scrape import scrape_and_enrich

# The twitter-api-client-v2 library installs uvloop's EventLoopPolicy at
# import time (triggered transitively via InfoExtractService → twitter).
# uvloop's policy raises RuntimeError from get_event_loop() if no loop
# exists, unlike stdlib asyncio which lazily creates one. ARQ's
# Worker.__init__ calls get_event_loop() before any loop is running.
#
# Fix: after all imports have completed (so uvloop policy is in place),
# create and set a loop using uvloop's own new_event_loop().
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())


def parse_redis_url(url: str) -> RedisSettings:
    """Parse a redis:// URL into ARQ RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
        conn_timeout=60,
        conn_retries=5,
        conn_retry_delay=1,
    )


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [scrape_and_enrich]
    redis_settings = parse_redis_url(settings.ARQ_REDIS_URL)

    # Job timeout: 10 minutes (matches existing Celery soft limit)
    job_timeout = 600

    # Maximum concurrent jobs
    max_jobs = 10

    # Retry jobs on transient failures (e.g. Redis timeout after task completes)
    retry_jobs = True
    max_tries = 3

    # Keep results for 1 hour
    keep_result = 3600

    # Health-check the Redis connection every 30s to prevent stale connections
    health_check_interval = 30

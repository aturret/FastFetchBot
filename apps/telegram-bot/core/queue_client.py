import uuid

from arq.connections import ArqRedis, create_pool, RedisSettings

from core.config import ARQ_REDIS_URL
from fastfetchbot_shared.utils.logger import logger

_arq_redis: ArqRedis | None = None
_bot_id: int | None = None


def _parse_redis_url(url: str) -> RedisSettings:
    """Parse a redis:// URL into ARQ RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


async def init(bot_id: int) -> None:
    """Initialize the ARQ Redis connection pool.

    Args:
        bot_id: Telegram bot user ID (from application.bot.id).
    """
    global _arq_redis, _bot_id
    if _arq_redis is None:
        _bot_id = bot_id
        _arq_redis = await create_pool(_parse_redis_url(ARQ_REDIS_URL))
        logger.info(f"ARQ queue client initialized for bot_id={bot_id}")


async def close() -> None:
    """Close the ARQ Redis connection pool."""
    global _arq_redis, _bot_id
    if _arq_redis is not None:
        await _arq_redis.aclose()
        _arq_redis = None
        _bot_id = None
        logger.info("ARQ queue client closed")


async def enqueue_scrape(
    url: str,
    chat_id: int | str,
    message_id: int | None = None,
    source: str = "",
    content_type: str = "",
    **kwargs,
) -> str:
    """Enqueue a scrape-and-enrich job to the ARQ worker.

    Returns the job_id (UUID string).
    """
    if _arq_redis is None or _bot_id is None:
        raise RuntimeError("Queue client not initialized. Call queue_client.init() first.")

    job_id = str(uuid.uuid4())
    await _arq_redis.enqueue_job(
        "scrape_and_enrich",
        url=url,
        chat_id=chat_id,
        job_id=job_id,
        message_id=message_id,
        source=source,
        content_type=content_type,
        bot_id=_bot_id,
        **kwargs,
    )
    logger.info(f"Enqueued scrape job: job_id={job_id}, url={url}")
    return job_id

import json

import redis.asyncio as aioredis

from async_worker.config import OUTBOX_REDIS_URL, OUTBOX_QUEUE_KEY
from fastfetchbot_shared.utils.logger import logger

_redis: aioredis.Redis | None = None


async def get_outbox_redis() -> aioredis.Redis:
    """Get or create the outbox Redis connection."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(OUTBOX_REDIS_URL, decode_responses=True)
    return _redis


async def push(
    job_id: str,
    chat_id: int | str,
    metadata_item: dict | None = None,
    message_id: int | None = None,
    error: str | None = None,
) -> None:
    """Push a result payload to the Redis outbox queue."""
    r = await get_outbox_redis()
    payload = {
        "job_id": job_id,
        "chat_id": chat_id,
        "message_id": message_id,
        "metadata_item": metadata_item,
        "error": error,
    }
    await r.lpush(OUTBOX_QUEUE_KEY, json.dumps(payload, ensure_ascii=False))
    logger.info(f"Pushed result to outbox: job_id={job_id}, error={error is not None}")


async def close() -> None:
    """Close the outbox Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None

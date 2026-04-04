import asyncio
import json

import redis.asyncio as aioredis

from async_worker.config import settings
from fastfetchbot_shared.utils.logger import logger

FILEID_QUEUE_KEY = "fileid:updates"
FILEID_DLQ_KEY = "fileid:updates:dlq"
_MAX_RETRIES = 3

_redis: aioredis.Redis | None = None
_consumer_task: asyncio.Task | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.OUTBOX_REDIS_URL, decode_responses=True)
    return _redis


async def _consume_loop() -> None:
    """Background loop: BRPOP from the file_id updates queue and persist to MongoDB."""
    r = await _get_redis()
    logger.info(f"file_id consumer started, listening on '{FILEID_QUEUE_KEY}'")

    while True:
        raw_payload = None
        try:
            result = await r.brpop(FILEID_QUEUE_KEY, timeout=0)
            if result is None:
                continue

            _, raw_payload = result
            payload = json.loads(raw_payload)
            await _process_file_id_update(payload)

        except asyncio.CancelledError:
            # Shutdown requested — requeue unprocessed payload so it isn't lost.
            if raw_payload is not None:
                try:
                    await r.lpush(FILEID_QUEUE_KEY, raw_payload)
                    logger.info("Requeued in-flight payload before shutdown")
                except Exception:
                    logger.warning(f"Failed to requeue payload on shutdown: {raw_payload}")
            logger.info("file_id consumer cancelled, shutting down")
            break
        except json.JSONDecodeError as e:
            # Permanent failure — payload is malformed, send to dead-letter queue.
            logger.error(f"Malformed JSON in file_id queue, moving to DLQ: {e}")
            try:
                await r.lpush(FILEID_DLQ_KEY, raw_payload)
            except Exception:
                logger.warning(f"Failed to push to DLQ: {raw_payload}")
        except Exception as e:
            # Transient failure (DB unavailable, network blip, etc.) — requeue
            # the payload so it can be retried on the next loop iteration.
            logger.error(f"file_id consumer error, requeuing payload: {e}")
            if raw_payload is not None:
                retry_count = 0
                try:
                    payload = json.loads(raw_payload)
                    retry_count = payload.get("_retry_count", 0)
                except (json.JSONDecodeError, TypeError):
                    pass

                if retry_count < _MAX_RETRIES:
                    try:
                        # Stamp retry count so we can detect repeated failures.
                        payload["_retry_count"] = retry_count + 1
                        await r.lpush(FILEID_QUEUE_KEY, json.dumps(payload, ensure_ascii=False))
                    except Exception:
                        logger.warning(f"Failed to requeue payload: {raw_payload}")
                else:
                    logger.error(f"Max retries ({_MAX_RETRIES}) exceeded, moving to DLQ: {raw_payload}")
                    try:
                        await r.lpush(FILEID_DLQ_KEY, raw_payload)
                    except Exception:
                        logger.warning(f"Failed to push to DLQ: {raw_payload}")
            await asyncio.sleep(1)


async def _process_file_id_update(payload: dict) -> None:
    """Update the latest Metadata document with telegram file_ids."""
    from fastfetchbot_shared.database.mongodb.models.metadata import Metadata

    metadata_url = payload.get("metadata_url", "")
    updates = payload.get("file_id_updates", [])

    if not metadata_url or not updates:
        logger.warning(f"Invalid file_id update payload: {payload}")
        return

    doc = await Metadata.find(
        Metadata.url == metadata_url
    ).sort("-version").limit(1).first_or_none()

    if doc is None or not doc.media_files:
        logger.warning(f"No metadata found for file_id update: {metadata_url}")
        return

    matched = 0
    for update in updates:
        for mf in doc.media_files:
            if mf.url == update["url"] and mf.telegram_file_id is None:
                mf.telegram_file_id = update["telegram_file_id"]
                matched += 1

    if matched > 0:
        await doc.save()
        logger.info(f"Updated {matched}/{len(updates)} file_ids for {metadata_url}")


async def start() -> None:
    """Start the file_id consumer as a background asyncio task."""
    global _consumer_task
    if _consumer_task is not None:
        logger.warning("file_id consumer already running")
        return
    _consumer_task = asyncio.create_task(_consume_loop())
    logger.info("file_id consumer task created")


async def stop() -> None:
    """Stop the file_id consumer and close the Redis connection."""
    global _consumer_task, _redis

    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None
        logger.info("file_id consumer task stopped")

    if _redis is not None:
        await _redis.aclose()
        _redis = None

import asyncio
import json

import redis.asyncio as aioredis

from core.config import settings
from core.services.message_sender import send_item_message
from fastfetchbot_shared.utils.logger import logger

_redis: aioredis.Redis | None = None
_consumer_task: asyncio.Task | None = None
_outbox_key: str | None = None


async def _get_redis() -> aioredis.Redis:
    """Get or create the outbox Redis connection."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.OUTBOX_REDIS_URL, decode_responses=True)
    return _redis


async def _consume_loop() -> None:
    """Background loop: BRPOP from the per-bot outbox queue and dispatch results."""
    r = await _get_redis()
    key = _outbox_key or settings.OUTBOX_QUEUE_KEY
    logger.info(f"Outbox consumer started, listening on '{key}'")

    while True:
        try:
            # BRPOP blocks until a message is available (timeout=0 means block forever)
            result = await r.brpop(key, timeout=0)
            if result is None:
                continue

            _, raw_payload = result
            payload = json.loads(raw_payload)

            job_id = payload.get("job_id", "unknown")
            chat_id = payload.get("chat_id")
            error = payload.get("error")

            if error:
                logger.warning(f"[{job_id}] Scrape failed: {error}")
                await _send_error_to_chat(chat_id, error)
            else:
                metadata_item = payload.get("metadata_item")
                if metadata_item and chat_id:
                    logger.info(f"[{job_id}] Delivering result to chat {chat_id}")
                    await send_item_message(
                        metadata_item, chat_id=chat_id,
                        message_id=payload.get("message_id"),
                    )
                else:
                    logger.warning(f"[{job_id}] Invalid payload: missing metadata_item or chat_id")

        except asyncio.CancelledError:
            logger.info("Outbox consumer cancelled, shutting down")
            break
        except Exception as e:
            logger.error(f"Outbox consumer error: {e}")
            # Brief pause before retrying to avoid tight error loops
            await asyncio.sleep(1)


async def _send_error_to_chat(chat_id: int | str, error: str) -> None:
    """Send an error notification to the user's chat."""
    try:
        from core.services.bot_app import application

        await application.bot.send_message(
            chat_id=chat_id,
            text=f"Sorry, an error occurred while processing your request:\n\n{error}",
        )
    except Exception as e:
        logger.error(f"Failed to send error message to chat {chat_id}: {e}")


async def start(bot_id: int) -> None:
    """Start the outbox consumer as a background asyncio task.

    Args:
        bot_id: Telegram bot user ID. Used to build the per-bot outbox key
                so each bot only consumes its own results.
    """
    global _consumer_task, _outbox_key
    if _consumer_task is not None:
        logger.warning("Outbox consumer already running")
        return
    _outbox_key = f"{settings.OUTBOX_QUEUE_KEY}:{bot_id}"
    _consumer_task = asyncio.create_task(_consume_loop())
    logger.info(f"Outbox consumer task created for bot_id={bot_id}")


async def stop() -> None:
    """Stop the outbox consumer and close the Redis connection."""
    global _consumer_task, _redis, _outbox_key

    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None
        logger.info("Outbox consumer task stopped")

    if _redis is not None:
        await _redis.aclose()
        _redis = None
    _outbox_key = None

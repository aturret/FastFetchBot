import json
from typing import Optional

import redis.asyncio as aioredis
from telegram import Message

from core.config import settings
from fastfetchbot_shared.utils.logger import logger

FILEID_QUEUE_KEY = "fileid:updates"

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.OUTBOX_REDIS_URL, decode_responses=True)
    return _redis


def extract_file_id(message: Message, media_type: str) -> Optional[str]:
    """Extract the telegram file_id from a sent Message based on media type."""
    if media_type == "image" and message.photo:
        return message.photo[-1].file_id
    elif media_type == "video" and message.video:
        return message.video.file_id
    elif media_type == "gif" and message.animation:
        return message.animation.file_id
    elif media_type == "audio" and message.audio:
        return message.audio.file_id
    elif media_type == "document" and message.document:
        return message.document.file_id
    return None


async def capture_and_push_file_ids(
    uncached_info: list[dict],
    sent_messages: tuple[Message, ...],
    metadata_url: str,
) -> None:
    """Extract file_ids from sent messages and push updates to Redis for the async worker.

    Args:
        uncached_info: list of {"url": str, "media_type": str} for items that were
            downloaded (not served from cached file_id). Parallel to sent_messages —
            each entry corresponds to a message at the same position.
        sent_messages: tuple of Message objects returned by send_media_group.
        metadata_url: the original scraped page URL, used as the key for MongoDB lookup.
    """
    file_id_updates = []

    for i, info in enumerate(uncached_info):
        if info is None:
            continue
        if i >= len(sent_messages):
            break
        file_id = extract_file_id(sent_messages[i], info["media_type"])
        if file_id:
            file_id_updates.append({
                "url": info["url"],
                "media_type": info["media_type"],
                "telegram_file_id": file_id,
            })

    if not file_id_updates:
        return

    try:
        r = await _get_redis()
        payload = json.dumps({
            "metadata_url": metadata_url,
            "file_id_updates": file_id_updates,
        }, ensure_ascii=False)
        await r.lpush(FILEID_QUEUE_KEY, payload)
        logger.info(f"Pushed {len(file_id_updates)} file_id updates for {metadata_url}")
    except Exception:
        logger.warning(f"Failed to push file_id updates for {metadata_url}")

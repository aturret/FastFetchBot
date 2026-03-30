"""MongoDB cache layer for scraped metadata.

Provides URL-based cache lookup with TTL support and versioned saves.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastfetchbot_shared.database.mongodb.models.metadata import Metadata
from fastfetchbot_shared.utils.logger import logger


async def find_cached(url: str, ttl_seconds: int) -> Optional[Metadata]:
    """Look up the latest cached Metadata document for a URL.

    Args:
        url: The URL to look up.
        ttl_seconds: Maximum age in seconds. ``0`` disables expiry
            (always returns the cached document if it exists).

    Returns:
        The cached Metadata document, or ``None`` if no valid cache entry exists.
    """
    doc = await (
        Metadata.find(Metadata.url == url)
        .sort(-Metadata.version)
        .limit(1)
        .first_or_none()
    )
    if doc is None:
        return None

    # ttl_seconds == 0 means never expire
    if ttl_seconds != 0:
        age = datetime.utcnow() - doc.timestamp
        if age > timedelta(seconds=ttl_seconds):
            logger.info(
                f"Cache expired for {url} (age={age}, ttl={ttl_seconds}s)"
            )
            return None

    logger.info(f"Cache hit for {url} (version={doc.version})")
    return doc


async def save_metadata(metadata_item: dict) -> Metadata:
    """Insert a new Metadata document with auto-incremented version.

    If a document with the same URL already exists, the new document's
    version is set to ``latest_version + 1``. Otherwise it starts at 1.

    Args:
        metadata_item: Scraper output dict (MetadataItem fields).
            Must contain a non-empty ``url`` key.

    Returns:
        The inserted Metadata document.

    Raises:
        ValueError: If ``url`` is missing or empty.
    """
    url = metadata_item.get("url", "")
    if not url or not url.strip():
        raise ValueError("metadata_item must contain a non-empty 'url'")

    latest = await (
        Metadata.find(Metadata.url == url)
        .sort(-Metadata.version)
        .limit(1)
        .first_or_none()
    )
    new_version = (latest.version + 1) if latest else 1
    metadata_item["version"] = new_version

    doc = Metadata.model_construct(**metadata_item)
    await Metadata.insert(doc)

    logger.info(f"Saved metadata for {url} (version={new_version})")
    return doc

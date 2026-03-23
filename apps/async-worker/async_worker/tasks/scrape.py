import uuid
import traceback

from fastfetchbot_shared.models.url_metadata import UrlMetadata
from fastfetchbot_shared.services.scrapers.common import InfoExtractService
from fastfetchbot_shared.utils.logger import logger
from async_worker.services import outbox, enrichment
from async_worker.celery_client import celery_app
from async_worker.config import DOWNLOAD_VIDEO_TIMEOUT


async def scrape_and_enrich(
    ctx: dict,
    url: str,
    chat_id: int | str,
    job_id: str | None = None,
    message_id: int | None = None,
    source: str = "",
    content_type: str = "",
    bot_id: int | str | None = None,
    store_telegraph: bool | None = None,
    store_document: bool | None = None,
    **kwargs,
) -> dict:
    """ARQ task: scrape a URL, enrich the result, and push to the outbox.

    Args:
        ctx: ARQ worker context.
        url: The URL to scrape.
        chat_id: Telegram chat ID for result delivery.
        job_id: Unique job identifier (generated if not provided).
        message_id: Optional Telegram message ID for reply threading.
        source: URL source platform (e.g. "twitter", "weibo").
        content_type: Content type (e.g. "social_media", "video").
        bot_id: Telegram bot user ID. Used to route results to the correct
                bot's outbox queue (``scrape:outbox:{bot_id}``).
        store_telegraph: Override Telegraph publishing flag.
        store_document: Override PDF export flag.
        **kwargs: Extra arguments passed to the scraper.
    """
    if job_id is None:
        job_id = str(uuid.uuid4())

    logger.info(f"[{job_id}] Starting scrape: url={url}, source={source}")

    try:
        # Build UrlMetadata and scrape
        url_metadata = UrlMetadata(
            url=url, source=source, content_type=content_type
        )
        service = InfoExtractService(
            url_metadata=url_metadata,
            store_telegraph=False,  # We handle enrichment separately
            store_document=False,
            celery_app=celery_app,
            timeout=DOWNLOAD_VIDEO_TIMEOUT,
            **kwargs,
        )
        metadata_item = await service.get_item()

        # Enrich: Telegraph, PDF
        metadata_item = await enrichment.enrich(
            metadata_item,
            store_telegraph=store_telegraph,
            store_document=store_document,
        )

        logger.info(f"[{job_id}] Scrape completed successfully")

        # Push to outbox (per-bot queue key)
        await outbox.push(
            job_id=job_id,
            chat_id=chat_id,
            message_id=message_id,
            metadata_item=metadata_item,
            bot_id=bot_id,
        )

        return {"job_id": job_id, "status": "success"}

    except Exception as e:
        logger.error(f"[{job_id}] Scrape failed: {e}")
        logger.error(traceback.format_exc())

        # Push error to outbox so the bot can notify the user
        await outbox.push(
            job_id=job_id,
            chat_id=chat_id,
            message_id=message_id,
            error=str(e),
            bot_id=bot_id,
        )

        return {"job_id": job_id, "status": "error", "error": str(e)}

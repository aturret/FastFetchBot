"""Enrichment steps applied after scraping: Telegraph publishing and PDF export."""

from fastfetchbot_shared.models.metadata_item import MessageType
from fastfetchbot_shared.services.telegraph import Telegraph
from fastfetchbot_shared.utils.logger import logger
from async_worker.config import settings


async def enrich(
    metadata_item: dict,
    store_telegraph: bool | None = None,
    store_document: bool | None = None,
    store_database: bool | None = None,
) -> dict:
    """Apply enrichment steps to a scraped metadata item.

    - Telegraph publishing
    - PDF export (via shared PdfExport → Celery worker)
    """
    if store_telegraph is None:
        store_telegraph = settings.STORE_TELEGRAPH
    if store_document is None:
        store_document = settings.STORE_DOCUMENT
    if store_database is None:
        store_database = settings.DATABASE_ON

    # Force Telegraph for long messages
    if metadata_item.get("message_type") == MessageType.LONG:
        store_telegraph = True
        logger.info("Message type is long, forcing Telegraph publish")

    # Telegraph publishing
    if store_telegraph:
        telegraph_item = Telegraph.from_dict(metadata_item)
        try:
            telegraph_url = await telegraph_item.get_telegraph()
        except Exception as e:
            logger.error(f"Error publishing to Telegraph: {e}")
            telegraph_url = ""
        metadata_item["telegraph_url"] = telegraph_url

    # PDF export via shared async wrapper → Celery worker
    if store_document or (
        not store_document and metadata_item.get("telegraph_url") == ""
    ):
        logger.info("Exporting to PDF via Celery worker")
        try:
            from fastfetchbot_shared.services.file_export.pdf_export import PdfExport
            from async_worker.celery_client import celery_app

            pdf_export = PdfExport(
                title=metadata_item["title"],
                html_string=metadata_item["content"],
                celery_app=celery_app,
                timeout=settings.DOWNLOAD_VIDEO_TIMEOUT,
            )
            output_filename = await pdf_export.export()
            metadata_item["media_files"].append(
                {
                    "media_type": "document",
                    "url": output_filename,
                    "caption": "",
                }
            )
        except Exception as e:
            logger.error(f"Error exporting PDF: {e}")

    # MongoDB persistence (versioned)
    if store_database:
        try:
            from fastfetchbot_shared.database.mongodb.cache import save_metadata

            await save_metadata(metadata_item)
        except Exception as e:
            logger.error(f"Error saving to MongoDB: {e}")

    metadata_item["title"] = metadata_item["title"].strip()
    return metadata_item

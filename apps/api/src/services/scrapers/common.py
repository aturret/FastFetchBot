from typing import Optional, Any

from src.models.database_model import Metadata
from fastfetchbot_shared.models.url_metadata import UrlMetadata
from fastfetchbot_shared.models.metadata_item import MessageType
from fastfetchbot_shared.services.scrapers.common import InfoExtractService as CoreInfoExtractService
from fastfetchbot_shared.services.telegraph import Telegraph
from src.services.file_export import video_download, document_export
from src.database import save_instances
from fastfetchbot_shared.utils.logger import logger
from src.config import settings


class InfoExtractService(CoreInfoExtractService):
    """API-layer service that adds Telegraph, PDF export, DB storage, and video download."""

    service_classes: dict = {
        **CoreInfoExtractService.service_classes,
        "youtube": video_download.VideoDownloader,
        "bilibili": video_download.VideoDownloader,
    }

    def __init__(
            self,
            url_metadata: UrlMetadata,
            data: Any = None,
            store_database: Optional[bool] = None,
            store_telegraph: Optional[bool] = True,
            store_document: Optional[bool] = False,
            **kwargs,
    ):
        if store_database is None:
            store_database = settings.DATABASE_ON
        super().__init__(
            url_metadata,
            data=data,
            store_database=store_database,
            store_telegraph=store_telegraph,
            store_document=store_document,
            **kwargs,
        )

    async def process_item(self, metadata_item: dict) -> dict:
        if metadata_item.get("message_type") == MessageType.LONG:
            self.store_telegraph = True
            logger.info("message type is long, store in telegraph")
        if self.store_telegraph:
            telegraph_item = Telegraph.from_dict(metadata_item)
            try:
                telegraph_url = await telegraph_item.get_telegraph()
            except Exception as e:
                logger.error(f"Error while getting telegraph: {e}")
                telegraph_url = ""
            metadata_item["telegraph_url"] = telegraph_url
        if self.store_document or (
                not self.store_document and metadata_item["telegraph_url"] == ""
        ):
            logger.info("store in document")
            try:
                pdf_document = document_export.pdf_export.PdfExport(
                    title=metadata_item["title"], html_string=metadata_item["content"]
                )
                output_filename = await pdf_document.export()
                metadata_item["media_files"].append(
                    {
                        "media_type": "document",
                        "url": output_filename,
                        "caption": "",
                    }
                )
            except Exception as e:
                logger.error(f"Error while exporting document: {e}")
        metadata_item["title"] = metadata_item["title"].strip()
        if self.store_database:
            logger.info("store in database")
            await save_instances(Metadata.model_construct(**metadata_item))
        return metadata_item

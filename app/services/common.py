from typing import Optional, Any

from app.models.database_model import Metadata
from app.models.url_metadata import UrlMetadata
from app.models.metadata_item import MetadataItem, MessageType
from app.services import (
    threads,
    twitter,
    instagram,
    weibo,
    telegraph,
    douban,
    zhihu,
    video_download,
    wechat,
    document_export,
)
from app.database import save_instances
from app.utils.logger import logger
from app.config import DATABASE_ON


class InfoExtractService(object):
    def __init__(
        self,
        url_metadata: UrlMetadata,
        data: Any = None,
        store_database: Optional[bool] = DATABASE_ON,
        store_telegraph: Optional[bool] = True,
        store_document: Optional[bool] = False,
        **kwargs,
    ):
        url_metadata = url_metadata.to_dict()
        self.url = url_metadata["url"]
        self.content_type = url_metadata["content_type"]
        self.source = url_metadata["source"]
        self.data = data
        self.service_classes = {
            "twitter": twitter.Twitter,
            "threads": threads.Threads,
            "weibo": weibo.Weibo,
            "wechat": wechat.Wechat,
            "instagram": instagram.Instagram,
            "douban": douban.Douban,
            "zhihu": zhihu.Zhihu,
            "youtube": video_download.VideoDownloader,
            "bilibili": video_download.VideoDownloader,
        }
        self.kwargs = kwargs
        self.store_database = store_database
        self.store_telegraph = store_telegraph
        self.store_document = store_document

    @property
    def category(self) -> str:
        return self.source

    async def get_item(self) -> dict:
        if self.content_type == "video":
            self.kwargs["category"] = self.category
        try:
            scraper_item = self.service_classes[self.category](self.url, **self.kwargs)
            metadata_item = await scraper_item.get_item()
        except Exception as e:
            logger.error(f"Error while getting item: {e}")
            raise e
        logger.info(f"Got metadata item")
        logger.debug(metadata_item)
        if metadata_item.get("message_type") == MessageType.LONG:
            self.store_telegraph = True
            logger.info("message type is long, store in telegraph")
        if self.store_telegraph:
            telegraph_item = telegraph.Telegraph.from_dict(metadata_item)
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
        if self.store_database:
            await save_instances(Metadata.from_dict(metadata_item))
        return metadata_item

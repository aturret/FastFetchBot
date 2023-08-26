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
        **kwargs
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
            "instagram": instagram.Instagram,
            "douban": douban.Douban,
            "zhihu": zhihu.Zhihu,
            "youtube": video_download.VideoDownloader,
            "bilibili": video_download.VideoDownloader,
        }
        self.kwargs = kwargs
        self.store_database = store_database
        self.store_telegraph = store_telegraph

    @property
    def category(self) -> str:
        return self.source

    async def get_item(self) -> dict:
        if self.content_type == "video":
            self.kwargs["category"] = self.category
        scraper_item = self.service_classes[self.category](self.url, **self.kwargs)
        metadata_item = await scraper_item.get_item()
        logger.debug(metadata_item)
        if metadata_item.get("message_type") == MessageType.LONG:
            self.store_telegraph = True
        if self.store_telegraph:
            telegraph_item = telegraph.Telegraph.from_dict(metadata_item)
            telegraph_url = await telegraph_item.get_telegraph()
            metadata_item["telegraph_url"] = telegraph_url
        if self.store_database:
            await save_instances(Metadata.from_dict(metadata_item))
        return metadata_item

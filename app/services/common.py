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
    def __init__(self,
                 url_metadata: UrlMetadata,
                 data: Any = None,
                 store_database: Optional[bool] = DATABASE_ON,
                 store_telegraph: Optional[bool] = True,
                 **kwargs):
        url_metadata = url_metadata.to_dict()
        self.url = url_metadata["url"]
        self.content_type = url_metadata["content_type"]
        self.source = url_metadata["source"]
        self.data = data
        self.service_functions = {
            "twitter": self.get_twitter,
            "threads": self.get_threads,
            "weibo": self.get_weibo,
            "instagram": self.get_instagram,
            "douban": self.get_douban,
            "zhihu": self.get_zhihu,
            "youtube": self.get_video,
            "bilibili": self.get_video,
        }
        self.kwargs = kwargs
        self.store_database = store_database
        self.store_telegraph = store_telegraph

    @property
    def category(self) -> str:
        return self.source

    async def get_item(self) -> dict:
        metadata_item = await self.service_functions[self.category]()
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

    async def get_threads(self) -> dict:
        threads_item = threads.Threads(self.url, **self.kwargs)
        metadata_item = await threads_item.get_threads()
        return metadata_item

    async def get_twitter(self) -> dict:
        twitter_item = twitter.Twitter(self.url, **self.kwargs)
        metadata_item = await twitter_item.get_twitter()
        return metadata_item

    async def get_weibo(self) -> dict:
        weibo_item = weibo.Weibo(self.url, **self.kwargs)
        metadata_item = await weibo_item.get_weibo()
        return metadata_item

    async def get_douban(self) -> dict:
        douban_item = douban.Douban(self.url, **self.kwargs)
        metadata_item = await douban_item.get_douban()
        return metadata_item

    async def get_zhihu(self) -> dict:
        zhihu_item = zhihu.Zhihu(self.url, **self.kwargs)
        metadata_item = await zhihu_item.get_zhihu()
        return metadata_item

    async def get_instagram(self) -> dict:
        pass

    async def get_video(self) -> dict:
        video_item = video_download.VideoDownloader(
            self.url, category=self.category, **self.kwargs
        )
        metadata_item = await video_item.get_video()
        return metadata_item

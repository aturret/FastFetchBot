from typing import Optional, Any

from app.models.url_metadata import UrlMetadata
from app.models.metadata_item import MetadataItem
from app.services import threads, twitter, instagram, weibo, telegraph


class InfoExtractService(object):
    def __init__(self, url_metadata: UrlMetadata, data: Any = None, **kwargs):
        url_metadata = url_metadata.to_dict()
        self.url = url_metadata["url"]
        self.type = url_metadata["type"]
        self.source = url_metadata["source"]
        self.category = self.check_category(self.source)
        self.data = data
        self.service_functions = {
            "instagram": self.get_instagram,
            "twitter": self.get_twitter,
            "threads": self.get_threads,
            "weibo": self.get_weibo,
            "youtube": self.get_video,
            "bilibili": self.get_video,
        }
        self.kwargs = kwargs

    @staticmethod
    def check_category(source: str) -> str:
        category = source
        return category

    async def get_item(self):
        metadata_item = await self.service_functions[self.category]()
        # TODO: check if metadata_item needs to create a telegraph page
        return metadata_item

    async def get_threads(self):
        threads_item = threads.Threads(self.url, **self.kwargs)
        metadata_item = await threads_item.get_threads()
        return metadata_item

    async def get_twitter(self):
        twitter_item = twitter.Twitter(self.url, **self.kwargs)
        metadata_item = await twitter_item.get_twitter()
        return metadata_item

    async def get_instagram(self):
        pass

    async def get_weibo(self):
        pass

    async def get_video(self):
        pass

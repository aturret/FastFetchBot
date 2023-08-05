from typing import Optional, Any

from app.models.url_metadata import UrlMetadata
from app.models.metadata_item import MetadataItem
from app.services import threads, twitter, instagram, weibo, telegraph, douban, zhihu


class InfoExtractService(object):
    def __init__(self, url_metadata: UrlMetadata, data: Any = None, **kwargs):
        url_metadata = url_metadata.to_dict()
        self.url = url_metadata["url"]
        self.type = url_metadata["type"]
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

    @property
    def category(self) -> str:
        return self.source

    async def get_item(self):
        metadata_item = await self.service_functions[self.category]()
        if metadata_item["type"] == "long":
            telegraph_item = telegraph.Telegraph.from_dict(metadata_item)
            telegraph_url = await telegraph_item.get_telegraph()
            metadata_item["telegraph_url"] = telegraph_url
        print(metadata_item)
        return metadata_item

    async def get_threads(self):
        threads_item = threads.Threads(self.url, **self.kwargs)
        metadata_item = await threads_item.get_threads()
        return metadata_item

    async def get_twitter(self):
        twitter_item = twitter.Twitter(self.url, **self.kwargs)
        metadata_item = await twitter_item.get_twitter()
        return metadata_item

    async def get_weibo(self):
        weibo_item = weibo.Weibo(self.url, **self.kwargs)
        metadata_item = await weibo_item.get_weibo()
        return metadata_item

    async def get_douban(self):
        douban_item = douban.Douban(self.url, **self.kwargs)
        metadata_item = await douban_item.get_douban()
        return metadata_item

    async def get_zhihu(self):
        zhihu_item = zhihu.Zhihu(self.url, **self.kwargs)
        metadata_item = await zhihu_item.get_zhihu()
        return metadata_item

    async def get_instagram(self):
        pass

    async def get_video(self):
        pass

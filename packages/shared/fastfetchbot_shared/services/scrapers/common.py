from typing import Optional, Any

from fastfetchbot_shared.models.url_metadata import UrlMetadata
from fastfetchbot_shared.services.scrapers import (
    twitter,
    wechat,
    reddit,
    weibo,
    zhihu,
    douban,
    instagram,
    xiaohongshu,
    threads,
)
from fastfetchbot_shared.services.scrapers.scraper_manager import ScraperManager
from fastfetchbot_shared.utils.logger import logger


class InfoExtractService(object):
    """Core scraping service — routes URLs to the correct scraper and returns raw metadata.

    This base class handles only scraping. Telegraph publishing, PDF export,
    DB storage, and video download are handled by subclasses (e.g. in the API app).
    """

    service_classes: dict = {
        "twitter": twitter.Twitter,
        "threads": threads.Threads,
        "reddit": reddit.Reddit,
        "weibo": weibo.Weibo,
        "wechat": wechat.Wechat,
        "instagram": instagram.Instagram,
        "douban": douban.Douban,
        "zhihu": zhihu.Zhihu,
        "xiaohongshu": xiaohongshu.Xiaohongshu,
    }

    def __init__(
            self,
            url_metadata: UrlMetadata,
            data: Any = None,
            store_database: Optional[bool] = False,
            store_telegraph: Optional[bool] = True,
            store_document: Optional[bool] = False,
            **kwargs,
    ):
        url_metadata = url_metadata.to_dict()
        self.url = url_metadata["url"]
        self.content_type = url_metadata["content_type"]
        self.source = url_metadata["source"]
        self.data = data
        self.kwargs = kwargs
        self.store_database = store_database
        self.store_telegraph = store_telegraph
        self.store_document = store_document

    @property
    def category(self) -> str:
        return self.source

    async def get_item(self, metadata_item: Optional[dict] = None) -> dict:
        if not metadata_item:
            try:
                if self.category in ["bluesky", "weibo", "other", "unknown"]:
                    await ScraperManager.init_scraper(self.category)
                    item_data_processor = await ScraperManager.scrapers[self.category].get_processor_by_url(url=self.url)
                    metadata_item = await item_data_processor.get_item()
                else:
                    scraper_item = self.service_classes[self.category](
                        url=self.url, data=self.data, **self.kwargs
                    )
                    metadata_item = await scraper_item.get_item()
            except Exception as e:
                logger.error(f"Error while getting item: {e}")
                raise e
        logger.info(f"Got metadata item")
        logger.debug(metadata_item)
        metadata_item = await self.process_item(metadata_item)
        return metadata_item

    async def process_item(self, metadata_item: dict) -> dict:
        """Base process_item — just strips title whitespace. Override for enrichment."""
        metadata_item["title"] = metadata_item["title"].strip()
        return metadata_item

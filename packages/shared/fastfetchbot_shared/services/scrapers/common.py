from typing import Optional, Any

from fastfetchbot_shared.models.url_metadata import UrlMetadata
from fastfetchbot_shared.exceptions import ScraperError
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

    This base class handles scraping for all platforms, including video sites
    (YouTube, Bilibili) via the shared VideoDownloader. Telegraph publishing,
    PDF export, and DB storage are handled by subclasses (e.g. in the API app).

    For video platforms, callers must pass ``celery_app`` and optionally
    ``timeout`` as keyword arguments so the VideoDownloader can submit Celery
    tasks for yt-dlp operations.
    """

    @staticmethod
    def _get_video_downloader():
        """Lazy import to avoid circular dependency (video_download → scrapers.config → scrapers → common)."""
        from fastfetchbot_shared.services.file_export.video_download import VideoDownloader
        return VideoDownloader

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
            database_cache_ttl: int = -1,
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
        self.database_cache_ttl = database_cache_ttl

    @property
    def category(self) -> str:
        return self.source

    def _resolve_scraper_class(self, category: str):
        """Look up scraper class, falling back to lazy VideoDownloader for video platforms."""
        if category in self.service_classes:
            return self.service_classes[category]
        if category in ("youtube", "bilibili"):
            return self._get_video_downloader()
        raise ScraperError(f"No scraper registered for category: {category}")

    async def get_item(self, metadata_item: Optional[dict] = None) -> dict:
        # Cache lookup: skip scraping entirely if a valid cached document exists
        if self.store_database and self.database_cache_ttl >= 0:
            try:
                from fastfetchbot_shared.database.mongodb.cache import find_cached

                cached = await find_cached(self.url, self.database_cache_ttl)
                if cached is not None:
                    logger.info("Cache hit, returning cached metadata")
                    result = cached.model_dump(mode="json", exclude={"id", "revision_id"})
                    result["_cached"] = True
                    return result
            except Exception as e:
                logger.error(f"Cache lookup failed, proceeding with scrape: {e}")

        if not metadata_item:
            try:
                if self.category in ["bluesky", "weibo", "other", "unknown"]:
                    await ScraperManager.init_scraper(self.category)
                    item_data_processor = await ScraperManager.scrapers[self.category].get_processor_by_url(url=self.url)
                    metadata_item = await item_data_processor.get_item()
                else:
                    scraper_cls = self._resolve_scraper_class(self.category)
                    scraper_item = scraper_cls(
                        url=self.url, category=self.category, data=self.data, **self.kwargs
                    )
                    metadata_item = await scraper_item.get_item()
            except Exception as e:
                logger.error(f"Error while getting item: {e}")
                raise
        logger.info(f"Got metadata item")
        logger.debug(metadata_item)
        metadata_item = await self.process_item(metadata_item)
        return metadata_item

    async def process_item(self, metadata_item: dict) -> dict:
        """Base process_item — just strips title whitespace. Override for enrichment."""
        metadata_item["title"] = metadata_item["title"].strip()
        return metadata_item

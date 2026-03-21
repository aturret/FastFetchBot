from fastfetchbot_shared.services.scrapers import (
    twitter,
    weibo,
    bluesky,
    reddit,
    xiaohongshu,
    zhihu,
    douban,
    instagram,
    threads,
    wechat,
    general,
)
from fastfetchbot_shared.services.scrapers.common import InfoExtractService
from fastfetchbot_shared.services.scrapers.scraper_manager import ScraperManager

__all__ = [
    "InfoExtractService",
    "ScraperManager",
    "twitter",
    "weibo",
    "bluesky",
    "reddit",
    "xiaohongshu",
    "zhihu",
    "douban",
    "instagram",
    "threads",
    "wechat",
    "general",
]

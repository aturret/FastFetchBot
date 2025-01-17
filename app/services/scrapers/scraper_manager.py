from typing import Optional

from app.utils.logger import logger
from app.services.scrapers.bluesky.scraper import BlueskyScraper
from app.services.scrapers.weibo.scraper import WeiboScraper
from app.config import (
    BLUESKY_USERNAME, BLUESKY_PASSWORD
)


class ScraperManager:

    bluesky_scraper: Optional[BlueskyScraper] = None
    weibo_scraper: Optional[WeiboScraper] = None

    scrapers = {"bluesky": bluesky_scraper,
                "weibo": bluesky_scraper}

    @classmethod
    async def init_scrapers(cls):
        await cls.init_bluesky_scraper()

    @classmethod
    async def init_scraper(cls, category: str) -> None:
        if category in cls.scrapers.keys():
            scraper = None
            if category == "bluesky" and not cls.bluesky_scraper:
                scraper = await cls.init_bluesky_scraper()
            elif category == "weibo" and not cls.weibo_scraper:
                scraper = await cls.init_weibo_scraper()
            if scraper:
                cls.scrapers[category] = scraper
        else:
            logger.error(f"Scraper {category} is not supported")
            raise ValueError(f"Scraper {category} is not supported")

    @classmethod
    async def init_bluesky_scraper(cls) -> BlueskyScraper:
        bluesky_scraper = BlueskyScraper(username=BLUESKY_USERNAME, password=BLUESKY_PASSWORD)
        await bluesky_scraper.init()
        return bluesky_scraper

    @classmethod
    async def init_weibo_scraper(cls) -> WeiboScraper:
        weibo_scraper = WeiboScraper()
        return weibo_scraper

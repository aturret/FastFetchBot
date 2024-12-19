from typing import Tuple

import pytest
import pytest_asyncio

from app.services.scrapers.weibo.scraper import WeiboScraper
from app.services.scrapers.scraper_manager import ScraperManager
from app.utils.logger import logger
from tests.cases.weibo import weibo_cases


@pytest_asyncio.fixture(scope="module", autouse=True)
async def weibo_scraper():
    weibo_scraper = await ScraperManager.init_weibo_scraper()
    return weibo_scraper


async def get_item_from_url(weibo_scraper: WeiboScraper, url: str) -> dict:
    data_processor = await weibo_scraper.get_processor_by_url(url)
    item = await data_processor.get_item()
    return item


async def get_test_data(weibo_scraper: WeiboScraper, case: str) -> Tuple[dict, dict]:
    data = await get_item_from_url(weibo_scraper=weibo_scraper, url=weibo_cases[case]["url"])
    return data, weibo_cases[case]["expected"]


@pytest.mark.asyncio
async def test_pure_short_text(weibo_scraper: WeiboScraper):
    data, expected = await get_test_data(weibo_scraper, "pure_short_text")
    assert True

from typing import Tuple

import pytest

from app.services.scrapers.bluesky.scraper import BlueskyScraper
from app.services.scrapers.scraper_manager import ScraperManager
from tests.cases.bluesky import bluesky_cases


@pytest.fixture(scope="module", autouse=True)
async def bluesky_scraper():
    bluesky_scraper = await ScraperManager.init_bluesky_scraper()
    yield bluesky_scraper


async def get_item_from_url(bluesky_scraper: BlueskyScraper, url: str) -> dict:
    data_processor = await bluesky_scraper.get_processor_by_url(url)
    item = await data_processor.get_item()
    return item


async def get_test_data(bluesky_scraper: BlueskyScraper, case: str) -> Tuple[dict, dict]:
    data = await get_item_from_url(bluesky_scraper=bluesky_scraper, url=bluesky_cases[case]["url"])
    return data, bluesky_cases[case]["expected"]


@pytest.mark.asyncio
async def test_bluesky_init(bluesky_scraper: BlueskyScraper):
    assert bluesky_scraper is not None
    assert isinstance(bluesky_scraper, BlueskyScraper)


@pytest.mark.asyncio
async def test_bluesky_pure_text_post(bluesky_scraper: BlueskyScraper):
    data, expected = await get_test_data(bluesky_scraper, "pure_text")
    assert data == expected

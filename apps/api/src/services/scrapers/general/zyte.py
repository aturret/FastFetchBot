from zyte_api import AsyncZyteAPI

from src.config import ZYTE_API_KEY
from src.services.scrapers.general.base import BaseGeneralDataProcessor, BaseGeneralScraper
from src.services.scrapers.scraper import DataProcessor
from fastfetchbot_shared.utils.logger import logger


class ZyteDataProcessor(BaseGeneralDataProcessor):
    """
    ZyteDataProcessor: Process URLs using Zyte API to extract content.
    """

    def __init__(self, url: str):
        super().__init__(url)
        self.scraper_type = "zyte"

    async def _get_page_content(self) -> None:
        if not ZYTE_API_KEY:
            raise RuntimeError("ZYTE_API_KEY is not configured")

        try:
            client = AsyncZyteAPI(api_key=ZYTE_API_KEY)
            result = await client.get(
                {
                    "url": self.url,
                    "browserHtml": True,
                    "article": True,
                    "articleOptions": {"extractFrom": "browserHtml"},
                }
            )
            await self._process_zyte_result(result)
        except Exception as e:
            logger.error(f"Failed to scrape URL with Zyte: {e}")
            raise

    async def _process_zyte_result(self, result: dict) -> None:
        article = result.get("article", {})
        browser_html = result.get("browserHtml", "")

        # Extract metadata fields from article
        title = article.get("headline", "") or article.get("name", "")

        # Extract author information
        authors = article.get("authors", [])
        author = authors[0].get("name", "") if authors else ""

        description = article.get("description", "") or article.get("articleBodyRaw", "")[:500]

        # Get article body as HTML
        article_body_html = article.get("articleBodyHtml", "")
        article_body_raw = article.get("articleBodyRaw", "")

        # Use article body HTML if available, otherwise fall back to browser HTML
        html_content = article_body_html if article_body_html else browser_html
        markdown_content = article_body_raw

        # Extract main image
        main_image = article.get("mainImage", {})
        og_image = main_image.get("url") if main_image else None

        await self._build_item_data(
            title=title,
            author=author,
            description=description,
            markdown_content=markdown_content,
            html_content=html_content,
            og_image=og_image,
        )


class ZyteScraper(BaseGeneralScraper):
    """
    ZyteScraper: Scraper implementation using Zyte API for generic URL scraping.
    """

    async def get_processor_by_url(self, url: str) -> DataProcessor:
        return ZyteDataProcessor(url)

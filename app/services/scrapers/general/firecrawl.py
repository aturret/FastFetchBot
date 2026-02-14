from app.config import FIRECRAWL_WAIT_FOR
from app.services.scrapers.general.base import BaseGeneralDataProcessor, BaseGeneralScraper
from app.services.scrapers.general.firecrawl_client import FirecrawlClient
from app.services.scrapers.scraper import DataProcessor
from app.utils.logger import logger

# HTML tags to exclude from Firecrawl output at the source
FIRECRAWL_EXCLUDE_TAGS = [
    "nav", "footer", "aside", "script", "style",
    "noscript", "iframe", "svg", "form",
]


class FirecrawlDataProcessor(BaseGeneralDataProcessor):
    """
    FirecrawlDataProcessor: Process URLs using Firecrawl to extract content.
    """

    def __init__(self, url: str):
        super().__init__(url)
        self.scraper_type = "firecrawl"
        self._client: FirecrawlClient = FirecrawlClient.get_instance()

    async def _get_page_content(self) -> None:
        try:
            result = self._client.scrape_url(
                url=self.url,
                formats=["markdown", "html"],
                only_main_content=True,
                exclude_tags=FIRECRAWL_EXCLUDE_TAGS,
                wait_for=FIRECRAWL_WAIT_FOR,
            )
            await self._process_firecrawl_result(result)
        except Exception as e:
            logger.error(f"Failed to scrape URL with Firecrawl: {e}")
            raise

    async def _process_firecrawl_result(self, result: dict) -> None:
        metadata = result.get("metadata", {})
        markdown_content = result.get("markdown", "")
        html_content = result.get("html", "")

        # Extract metadata fields
        title = metadata.get("title", "") or metadata.get("ogTitle", "")
        author = metadata.get("author", "") or metadata.get("ogSiteName", "")
        description = metadata.get("description", "") or metadata.get("ogDescription", "")
        og_image = metadata.get("ogImage")

        await self._build_item_data(
            title=title,
            author=author,
            description=description,
            markdown_content=markdown_content,
            html_content=html_content,
            og_image=og_image,
        )


class FirecrawlScraper(BaseGeneralScraper):
    """
    FirecrawlScraper: Scraper implementation using Firecrawl for generic URL scraping.
    """

    async def get_processor_by_url(self, url: str) -> DataProcessor:
        return FirecrawlDataProcessor(url)

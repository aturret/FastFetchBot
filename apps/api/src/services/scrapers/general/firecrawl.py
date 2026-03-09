from typing import Optional

from src.config import FIRECRAWL_WAIT_FOR, FIRECRAWL_USE_JSON_EXTRACTION
from src.services.scrapers.general.base import BaseGeneralDataProcessor, BaseGeneralScraper
from src.services.scrapers.general.firecrawl_client import FirecrawlClient
from src.services.scrapers.general.firecrawl_schema import (
    ExtractedArticle,
    FIRECRAWL_EXTRACTION_PROMPT,
)
from src.services.scrapers.scraper import DataProcessor
from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.parse import get_html_text_length, wrap_text_into_html

# HTML tags to exclude from Firecrawl output at the source
FIRECRAWL_EXCLUDE_TAGS = [
    "nav", "footer", "aside", "script", "style",
    "noscript", "iframe", "svg", "form",
]

GENERAL_TEXT_LIMIT = 800


class FirecrawlDataProcessor(BaseGeneralDataProcessor):
    """
    FirecrawlDataProcessor: Process URLs using Firecrawl to extract content.

    Supports two modes:
      - Legacy: markdown + HTML with OpenAI LLM cleaning (default)
      - JSON extraction: Firecrawl's built-in LLM extraction
    """

    def __init__(self, url: str, use_json_extraction: Optional[bool] = None):
        super().__init__(url)
        self.scraper_type = "firecrawl"
        self._client: FirecrawlClient = FirecrawlClient.get_instance()
        self._use_json_extraction = (
            use_json_extraction
            if use_json_extraction is not None
            else FIRECRAWL_USE_JSON_EXTRACTION
        )

    async def _get_page_content(self) -> None:
        try:
            if self._use_json_extraction:
                await self._get_page_content_json()
            else:
                await self._get_page_content_legacy()
        except Exception as e:
            logger.error(f"Failed to scrape URL with Firecrawl: {e}")
            raise

    async def _get_page_content_legacy(self) -> None:
        """Original flow: markdown + HTML with OpenAI cleaning."""
        result = await self._client.scrape_url(
            url=self.url,
            formats=["markdown", "html"],
            only_main_content=True,
            exclude_tags=FIRECRAWL_EXCLUDE_TAGS,
            wait_for=FIRECRAWL_WAIT_FOR,
        )
        await self._process_firecrawl_result(result)

    async def _get_page_content_json(self) -> None:
        """JSON extraction flow with fallback to legacy processing."""
        json_format = {
            "type": "json",
            "schema": ExtractedArticle,
            "prompt": FIRECRAWL_EXTRACTION_PROMPT,
        }
        result = await self._client.scrape_url(
            url=self.url,
            formats=["html", json_format],
            only_main_content=True,
            exclude_tags=FIRECRAWL_EXCLUDE_TAGS,
            wait_for=FIRECRAWL_WAIT_FOR,
        )

        json_data = result.get("json")
        if json_data and isinstance(json_data, dict):
            await self._process_json_extraction(json_data, result)
        else:
            logger.warning(
                "Firecrawl JSON extraction returned no data, "
                "falling back to HTML processing"
            )
            await self._process_firecrawl_result(result)

    async def _process_json_extraction(
        self, json_data: dict, full_result: dict
    ) -> None:
        """Build item data from Firecrawl's JSON extraction response."""
        metadata = full_result.get("metadata", {})

        title = json_data.get("title", "") or metadata.get("title", "")
        author = json_data.get("author", "") or metadata.get("author", "")
        author_url = json_data.get("author_url") or (
            f"{self.url_parser.scheme}://{self.url_parser.netloc}"
        )
        text = json_data.get("text", "")
        content_html = json_data.get("content", "")

        # Convert extracted media files to MediaFile objects
        media_files = []
        for mf in json_data.get("media_files", []):
            media_files.append(
                MediaFile(
                    media_type=mf.get("media_type", "image"),
                    url=mf.get("url", ""),
                    original_url=mf.get("original_url"),
                    caption=mf.get("caption"),
                )
            )

        # Fall back to og:image if no media files were extracted
        if not media_files:
            og_image = metadata.get("ogImage") or metadata.get("og_image")
            if og_image:
                media_files.append(MediaFile(url=og_image, media_type="image"))

        # Sanitize and wrap content HTML
        if content_html:
            content_html = self.sanitize_html(content_html)
            content = wrap_text_into_html(content_html, is_html=True)
        else:
            markdown_content = full_result.get("markdown", "")
            content = wrap_text_into_html(markdown_content, is_html=False)

        self._data = {
            "id": self.id,
            "category": "other",
            "url": self.url,
            "title": title or self.url,
            "author": author or self.url_parser.netloc,
            "author_url": author_url,
            "text": text[:500] if text else "",
            "content": content,
            "raw_content": full_result.get("markdown", ""),
            "media_files": [m.to_dict() for m in media_files],
            "message_type": (
                MessageType.LONG
                if get_html_text_length(content) > GENERAL_TEXT_LIMIT
                else MessageType.SHORT
            ),
            "scraper_type": self.scraper_type,
        }

    async def _process_firecrawl_result(self, result: dict) -> None:
        """Process markdown + HTML response (legacy flow)."""
        metadata = result.get("metadata", {})
        markdown_content = result.get("markdown", "")
        html_content = result.get("html", "")

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

import hashlib
from urllib.parse import urlparse

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

from app.config import OPENAI_API_KEY
from app.models.metadata_item import MediaFile, MessageType
from app.services.scrapers.scraper import Scraper, DataProcessor
from app.services.scrapers.firecrawl_client import FirecrawlItem
from app.services.scrapers.firecrawl_client.client import FirecrawlClient
from app.utils.parse import get_html_text_length, wrap_text_into_html
from app.utils.logger import logger

FIRECRAWL_TEXT_LIMIT = 800

# System prompt for LLM to extract article content
ARTICLE_EXTRACTION_PROMPT = """You are an expert content extractor. Your task is to extract the main article content from the provided HTML.

Instructions:
1. Identify and extract ONLY the main article/post content
2. Remove navigation, headers, footers, sidebars, ads, comments, and other non-article elements
3. Preserve the article's structure (headings, paragraphs, lists, etc.)
4. Keep important formatting like bold, italic, links, and images
5. Return clean HTML containing only the article content
6. If you cannot identify the main content, return the original HTML unchanged

Return ONLY the extracted HTML content, no explanations or markdown."""


class FirecrawlDataProcessor(DataProcessor):
    """
    FirecrawlDataProcessor: Process URLs using Firecrawl to extract content.
    """

    def __init__(self, url: str):
        self.url: str = url
        self._data: dict = {}
        self.url_parser = urlparse(url)
        self.id = hashlib.md5(url.encode()).hexdigest()[:16]
        self._client: FirecrawlClient = FirecrawlClient.get_instance()

    async def get_item(self) -> dict:
        await self.process_data()
        firecrawl_item = FirecrawlItem.from_dict(self._data)
        return firecrawl_item.to_dict()

    async def process_data(self) -> None:
        await self._get_page_content()

    async def _get_page_content(self) -> None:
        try:
            result = self._client.scrape_url(
                url=self.url,
                formats=["markdown", "html"],
                only_main_content=True,
            )
            await self._process_firecrawl_result(result)
        except Exception as e:
            logger.error(f"Failed to scrape URL with Firecrawl: {e}")
            raise

    @staticmethod
    async def parsing_article_body_by_llm(html_content: str) -> str:
        """
        Use LLM to extract the main article content from HTML.

        Args:
            html_content: Raw HTML content from Firecrawl

        Returns:
            Cleaned HTML containing only the main article content
        """
        if not html_content:
            return html_content

        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured, skipping LLM parsing")
            return html_content

        try:
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)

            # Truncate content if too long to avoid token limits
            max_content_length = 50000
            truncated_content = html_content[:max_content_length] if len(html_content) > max_content_length else html_content

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    ChatCompletionSystemMessageParam(role="system", content=ARTICLE_EXTRACTION_PROMPT),
                    ChatCompletionUserMessageParam(role="user", content=f"Extract the main article content from this HTML:\n\n{truncated_content}")
                ],
                temperature=0.1,
                max_tokens=16000,
            )

            extracted_content = response.choices[0].message.content

            if extracted_content:
                logger.info("Successfully extracted article content using LLM")
                return extracted_content.strip()
            else:
                logger.warning("LLM returned empty content, using original HTML")
                return html_content

        except Exception as e:
            logger.error(f"Failed to parse article body with LLM: {e}")
            return html_content

    async def _process_firecrawl_result(self, result: dict) -> None:
        metadata = result.get("metadata", {})
        markdown_content = result.get("markdown", "")
        html_content = result.get("html", "")

        # Extract metadata fields
        title = metadata.get("title", "") or metadata.get("ogTitle", "") or self.url
        author = metadata.get("author", "") or metadata.get("ogSiteName", "") or self.url_parser.netloc
        description = metadata.get("description", "") or metadata.get("ogDescription", "")

        item_data = {
            "id": self.id,
            "category": "other",
            "url": self.url,
            "title": title,
            "author": author,
            "author_url": f"{self.url_parser.scheme}://{self.url_parser.netloc}",
        }

        # Process text content - use description or first part of markdown
        text = description if description else markdown_content[:500]
        item_data["text"] = text

        html_content = await self.parsing_article_body_by_llm(html_content)

        # Process HTML content
        if html_content:
            content = wrap_text_into_html(html_content, is_html=True)
        else:
            content = wrap_text_into_html(markdown_content, is_html=False)
        item_data["content"] = content
        item_data["raw_content"] = markdown_content

        # Process media files - extract og:image if available
        media_files = []
        og_image = metadata.get("ogImage")
        if og_image:
            media_files.append(MediaFile(url=og_image, media_type="image"))

        item_data["media_files"] = [m.to_dict() for m in media_files]

        # Determine message type based on text length
        item_data["message_type"] = (
            MessageType.LONG
            if get_html_text_length(content) > FIRECRAWL_TEXT_LIMIT
            else MessageType.SHORT
        )

        self._data = item_data


class FirecrawlScraper(Scraper):
    """
    FirecrawlScraper: Scraper implementation using Firecrawl for generic URL scraping.
    """

    async def get_processor_by_url(self, url: str) -> DataProcessor:
        return FirecrawlDataProcessor(url)

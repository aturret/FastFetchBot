"""Tests for packages/shared/fastfetchbot_shared/services/scrapers/general/zyte.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.services.scrapers.general.zyte import (
    ZyteDataProcessor,
    ZyteScraper,
)
from fastfetchbot_shared.exceptions import ExternalServiceError


# ---------------------------------------------------------------------------
# ZyteDataProcessor.__init__
# ---------------------------------------------------------------------------


class TestZyteDataProcessorInit:
    def test_init(self):
        proc = ZyteDataProcessor("https://example.com/page")
        assert proc.url == "https://example.com/page"
        assert proc.scraper_type == "zyte"
        assert proc._data == {}


# ---------------------------------------------------------------------------
# ZyteDataProcessor._get_page_content
# ---------------------------------------------------------------------------


class TestZyteGetPageContent:
    @pytest.mark.asyncio
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.ZYTE_API_KEY",
        None,
    )
    async def test_no_api_key_raises(self):
        proc = ZyteDataProcessor("https://example.com")
        with pytest.raises(ExternalServiceError, match="ZYTE_API_KEY is not configured"):
            await proc._get_page_content()

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.ZYTE_API_KEY", "zyte-key")
    @patch("fastfetchbot_shared.services.scrapers.general.zyte.AsyncZyteAPI")
    async def test_success(self, mock_zyte_cls):
        mock_client = AsyncMock()
        mock_zyte_cls.return_value = mock_client
        mock_client.get.return_value = {
            "article": {
                "headline": "Title",
                "authors": [{"name": "Author"}],
                "description": "Desc",
                "articleBodyHtml": "<p>body</p>",
                "articleBodyRaw": "raw body",
                "mainImage": {"url": "https://img.com/pic.jpg"},
            },
            "browserHtml": "<html><body>full</body></html>",
        }
        proc = ZyteDataProcessor("https://example.com/article")
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._get_page_content()
            mock_build.assert_awaited_once()
            kw = mock_build.call_args.kwargs
            assert kw["title"] == "Title"
            assert kw["author"] == "Author"
            assert kw["description"] == "Desc"
            assert kw["html_content"] == "<p>body</p>"
            assert kw["markdown_content"] == "raw body"
            assert kw["og_image"] == "https://img.com/pic.jpg"

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.ZYTE_API_KEY", "zyte-key")
    @patch("fastfetchbot_shared.services.scrapers.general.zyte.AsyncZyteAPI")
    async def test_exception_propagates(self, mock_zyte_cls):
        mock_client = AsyncMock()
        mock_zyte_cls.return_value = mock_client
        mock_client.get.side_effect = RuntimeError("zyte failure")
        proc = ZyteDataProcessor("https://example.com")
        with pytest.raises(RuntimeError):
            await proc._get_page_content()


# ---------------------------------------------------------------------------
# ZyteDataProcessor._process_zyte_result
# ---------------------------------------------------------------------------


class TestProcessZyteResult:
    @pytest.mark.asyncio
    async def test_full_article(self):
        proc = ZyteDataProcessor("https://example.com/article")
        result = {
            "article": {
                "headline": "Headline",
                "name": "Name",
                "authors": [{"name": "Writer"}],
                "description": "Short desc",
                "articleBodyHtml": "<p>body html</p>",
                "articleBodyRaw": "body raw",
                "mainImage": {"url": "https://img.com/main.jpg"},
            },
            "browserHtml": "<html>full</html>",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_zyte_result(result)
            kw = mock_build.call_args.kwargs
            assert kw["title"] == "Headline"
            assert kw["author"] == "Writer"
            assert kw["og_image"] == "https://img.com/main.jpg"

    @pytest.mark.asyncio
    async def test_fallback_to_name_when_no_headline(self):
        proc = ZyteDataProcessor("https://example.com/article")
        result = {
            "article": {
                "name": "Fallback Name",
                "authors": [],
                "articleBodyHtml": "",
                "articleBodyRaw": "raw",
                "description": "",
            },
            "browserHtml": "<html>browser</html>",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_zyte_result(result)
            kw = mock_build.call_args.kwargs
            assert kw["title"] == "Fallback Name"
            assert kw["author"] == ""
            # Falls back to browserHtml when articleBodyHtml is empty
            assert kw["html_content"] == "<html>browser</html>"

    @pytest.mark.asyncio
    async def test_no_authors(self):
        proc = ZyteDataProcessor("https://example.com/article")
        result = {
            "article": {
                "headline": "T",
                "authors": [],
                "articleBodyHtml": "<p>b</p>",
                "articleBodyRaw": "b",
            },
            "browserHtml": "",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_zyte_result(result)
            assert mock_build.call_args.kwargs["author"] == ""

    @pytest.mark.asyncio
    async def test_no_main_image(self):
        proc = ZyteDataProcessor("https://example.com/article")
        result = {
            "article": {
                "headline": "T",
                "authors": [],
                "articleBodyHtml": "<p>b</p>",
                "articleBodyRaw": "b",
            },
            "browserHtml": "",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_zyte_result(result)
            assert mock_build.call_args.kwargs["og_image"] is None

    @pytest.mark.asyncio
    async def test_empty_main_image_dict(self):
        proc = ZyteDataProcessor("https://example.com/article")
        result = {
            "article": {
                "headline": "T",
                "authors": [],
                "articleBodyHtml": "<p>b</p>",
                "articleBodyRaw": "b",
                "mainImage": {},
            },
            "browserHtml": "",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_zyte_result(result)
            assert mock_build.call_args.kwargs["og_image"] is None

    @pytest.mark.asyncio
    async def test_description_fallback_to_article_body_raw(self):
        proc = ZyteDataProcessor("https://example.com/article")
        long_raw = "x" * 600
        result = {
            "article": {
                "headline": "T",
                "authors": [],
                "description": "",
                "articleBodyHtml": "<p>b</p>",
                "articleBodyRaw": long_raw,
            },
            "browserHtml": "",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_zyte_result(result)
            desc = mock_build.call_args.kwargs["description"]
            assert len(desc) == 500

    @pytest.mark.asyncio
    async def test_empty_article(self):
        proc = ZyteDataProcessor("https://example.com/article")
        result = {
            "article": {},
            "browserHtml": "<html>page</html>",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_zyte_result(result)
            kw = mock_build.call_args.kwargs
            assert kw["title"] == ""
            assert kw["author"] == ""
            assert kw["html_content"] == "<html>page</html>"


# ---------------------------------------------------------------------------
# ZyteScraper
# ---------------------------------------------------------------------------


class TestZyteScraper:
    @pytest.mark.asyncio
    async def test_get_processor_by_url(self):
        scraper = ZyteScraper()
        processor = await scraper.get_processor_by_url("https://example.com/page")
        assert isinstance(processor, ZyteDataProcessor)
        assert processor.url == "https://example.com/page"

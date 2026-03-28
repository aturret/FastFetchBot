"""Tests for firecrawl.py and firecrawl_client.py in general scrapers."""

import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.services.scrapers.general.firecrawl_client import (
    FirecrawlClient,
    FirecrawlSettings,
)
from fastfetchbot_shared.exceptions import ExternalServiceError


# ---------------------------------------------------------------------------
# FirecrawlSettings (frozen dataclass)
# ---------------------------------------------------------------------------


class TestFirecrawlSettings:
    def test_create(self):
        s = FirecrawlSettings(api_url="https://api.firecrawl.dev", api_key="key123")
        assert s.api_url == "https://api.firecrawl.dev"
        assert s.api_key == "key123"

    def test_frozen(self):
        s = FirecrawlSettings(api_url="x", api_key="y")
        with pytest.raises(AttributeError):
            s.api_url = "z"


# ---------------------------------------------------------------------------
# FirecrawlClient singleton
# ---------------------------------------------------------------------------


class TestFirecrawlClientSingleton:
    def setup_method(self):
        FirecrawlClient.reset_instance()

    def teardown_method(self):
        FirecrawlClient.reset_instance()

    @patch("fastfetchbot_shared.services.scrapers.general.firecrawl_client.AsyncFirecrawl")
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_URL",
        "https://fc.example.com",
    )
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_KEY",
        "test-key",
    )
    def test_get_instance_creates_singleton(self, mock_fc_cls):
        mock_fc_cls.return_value = MagicMock()
        instance1 = FirecrawlClient.get_instance()
        instance2 = FirecrawlClient.get_instance()
        assert instance1 is instance2
        # AsyncFirecrawl called once (on first get_instance)
        mock_fc_cls.assert_called_once()

    @patch("fastfetchbot_shared.services.scrapers.general.firecrawl_client.AsyncFirecrawl")
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_URL",
        "https://fc.example.com",
    )
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_KEY",
        "test-key",
    )
    def test_reset_instance(self, mock_fc_cls):
        mock_fc_cls.return_value = MagicMock()
        inst1 = FirecrawlClient.get_instance()
        FirecrawlClient.reset_instance()
        inst2 = FirecrawlClient.get_instance()
        assert inst1 is not inst2

    @patch("fastfetchbot_shared.services.scrapers.general.firecrawl_client.AsyncFirecrawl")
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_URL",
        "https://fc.example.com",
    )
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_KEY",
        "test-key",
    )
    def test_double_check_locking_inner_branch(self, mock_fc_cls):
        """Cover the second `if cls._instance is not None` (line 48-49) inside the lock.

        We replace the lock with a wrapper that sets _instance after __enter__,
        simulating another thread having created the instance while we waited.
        """
        mock_fc_cls.return_value = MagicMock()
        sentinel = MagicMock()

        original_lock = FirecrawlClient._lock

        class SneakyLock:
            def __enter__(self_lock):
                original_lock.__enter__()
                FirecrawlClient._instance = sentinel
                return self_lock

            def __exit__(self_lock, *args):
                original_lock.__exit__(*args)

        FirecrawlClient._lock = SneakyLock()
        try:
            inst = FirecrawlClient.get_instance()
            assert inst is sentinel
        finally:
            FirecrawlClient._lock = original_lock


# ---------------------------------------------------------------------------
# FirecrawlClient.scrape_url
# ---------------------------------------------------------------------------


class TestFirecrawlClientScrapeUrl:
    def setup_method(self):
        FirecrawlClient.reset_instance()

    def teardown_method(self):
        FirecrawlClient.reset_instance()

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.firecrawl_client.AsyncFirecrawl")
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_URL",
        "https://fc.example.com",
    )
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_KEY",
        "k",
    )
    async def test_scrape_url_success(self, mock_fc_cls):
        mock_app = AsyncMock()
        mock_fc_cls.return_value = mock_app
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"markdown": "hello", "html": "<p>hello</p>"}
        mock_app.scrape.return_value = mock_result

        client = FirecrawlClient.get_instance()
        result = await client.scrape_url(
            url="https://example.com",
            formats=["markdown", "html"],
            only_main_content=True,
            exclude_tags=["nav"],
            wait_for=3000,
        )
        assert result == {"markdown": "hello", "html": "<p>hello</p>"}
        mock_app.scrape.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.firecrawl_client.AsyncFirecrawl")
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_URL",
        "https://fc.example.com",
    )
    @patch(
        "fastfetchbot_shared.services.scrapers.config.settings.FIRECRAWL_API_KEY",
        "k",
    )
    async def test_scrape_url_exception(self, mock_fc_cls):
        mock_app = AsyncMock()
        mock_fc_cls.return_value = mock_app
        mock_app.scrape.side_effect = Exception("network error")

        client = FirecrawlClient.get_instance()
        with pytest.raises(ExternalServiceError, match="Firecrawl scrape_url failed"):
            await client.scrape_url(url="https://fail.com")


# ---------------------------------------------------------------------------
# _is_content_truncated
# ---------------------------------------------------------------------------


class TestIsContentTruncated:
    def test_not_truncated(self):
        from fastfetchbot_shared.services.scrapers.general.firecrawl import _is_content_truncated
        assert _is_content_truncated("<p>abcdefghij</p>", "<p>abcdefghij</p>") is False

    def test_truncated(self):
        from fastfetchbot_shared.services.scrapers.general.firecrawl import _is_content_truncated
        short = "<p>ab</p>"
        long = "<p>" + "x" * 100 + "</p>"
        assert _is_content_truncated(short, long) is True

    def test_raw_zero_length(self):
        from fastfetchbot_shared.services.scrapers.general.firecrawl import _is_content_truncated
        assert _is_content_truncated("<p>abc</p>", "") is False

    def test_exact_threshold(self):
        """Ratio exactly at threshold is not truncated."""
        from fastfetchbot_shared.services.scrapers.general.firecrawl import (
            _is_content_truncated,
            _TRUNCATION_RATIO_THRESHOLD,
        )
        # 40 chars extracted out of 100 raw = ratio 0.4 exactly
        raw = "x" * 100
        extracted = "x" * 40
        assert _is_content_truncated(extracted, raw) is False


# ---------------------------------------------------------------------------
# FirecrawlDataProcessor
# ---------------------------------------------------------------------------


class TestFirecrawlDataProcessor:
    def setup_method(self):
        FirecrawlClient.reset_instance()

    def teardown_method(self):
        FirecrawlClient.reset_instance()

    def _make_processor(self, url="https://example.com/article", use_json=None):
        with patch(
            "fastfetchbot_shared.services.scrapers.general.firecrawl_client.FirecrawlClient.get_instance"
        ) as mock_gi:
            mock_client = MagicMock()
            mock_gi.return_value = mock_client
            from fastfetchbot_shared.services.scrapers.general.firecrawl import FirecrawlDataProcessor
            proc = FirecrawlDataProcessor(url, use_json_extraction=use_json)
            return proc, mock_client

    def test_init_default(self):
        proc, _ = self._make_processor()
        assert proc.scraper_type == "firecrawl"
        assert proc.url == "https://example.com/article"

    def test_init_use_json_explicit(self):
        proc, _ = self._make_processor(use_json=True)
        assert proc._use_json_extraction is True

    @pytest.mark.asyncio
    async def test_get_page_content_legacy(self):
        proc, mock_client = self._make_processor(use_json=False)
        mock_client.scrape_url = AsyncMock(return_value={
            "metadata": {"title": "T", "author": "A", "description": "D"},
            "markdown": "md",
            "html": "<p>html</p>",
        })
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._get_page_content()
            mock_build.assert_awaited_once()
            call_kw = mock_build.call_args.kwargs
            assert call_kw["title"] == "T"

    @pytest.mark.asyncio
    async def test_get_page_content_json_with_data(self):
        proc, mock_client = self._make_processor(use_json=True)
        mock_client.scrape_url = AsyncMock(return_value={
            "json": {
                "title": "JSON Title",
                "author": "JSON Author",
                "author_url": "https://example.com/author",
                "text": "summary",
                "content": "<p>" + "x" * 1000 + "</p>",
                "media_files": [
                    {"media_type": "image", "url": "https://img.com/1.jpg", "caption": "cap"},
                ],
            },
            "metadata": {"title": "meta title"},
            "html": "<p>" + "x" * 1000 + "</p>",
            "markdown": "md",
        })
        await proc._get_page_content()
        assert proc._data["title"] == "JSON Title"
        assert proc._data["author"] == "JSON Author"
        assert len(proc._data["media_files"]) == 1

    @pytest.mark.asyncio
    async def test_get_page_content_json_no_data_falls_back(self):
        proc, mock_client = self._make_processor(use_json=True)
        mock_client.scrape_url = AsyncMock(return_value={
            "json": None,
            "metadata": {"title": "T", "ogSiteName": "Site"},
            "markdown": "md",
            "html": "<p>html</p>",
        })
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._get_page_content()
            mock_build.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_page_content_exception(self):
        proc, mock_client = self._make_processor(use_json=False)
        mock_client.scrape_url = AsyncMock(side_effect=RuntimeError("fail"))
        with pytest.raises(RuntimeError):
            await proc._get_page_content()

    @pytest.mark.asyncio
    async def test_process_firecrawl_result_og_metadata_fallbacks(self):
        proc, _ = self._make_processor()
        result = {
            "metadata": {
                "ogTitle": "OG Title",
                "ogSiteName": "OG Site",
                "ogDescription": "OG Desc",
                "ogImage": "https://img.com/og.jpg",
            },
            "markdown": "md",
            "html": "<p>h</p>",
        }
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock) as mock_build:
            await proc._process_firecrawl_result(result)
            kw = mock_build.call_args.kwargs
            assert kw["title"] == "OG Title"
            assert kw["author"] == "OG Site"
            assert kw["description"] == "OG Desc"
            assert kw["og_image"] == "https://img.com/og.jpg"

    @pytest.mark.asyncio
    async def test_process_json_extraction_no_media_with_og_image(self):
        proc, _ = self._make_processor(use_json=True)
        json_data = {
            "title": "T",
            "author": "",
            "text": "t",
            "content": "<p>" + "a" * 500 + "</p>",
            "media_files": [],
        }
        full_result = {
            "metadata": {"ogImage": "https://og.com/img.png"},
            "html": "<p>" + "a" * 500 + "</p>",
            "markdown": "md",
        }
        await proc._process_json_extraction(json_data, full_result)
        # Should fall back to ogImage
        assert len(proc._data["media_files"]) == 1
        assert proc._data["media_files"][0]["url"] == "https://og.com/img.png"

    @pytest.mark.asyncio
    async def test_process_json_extraction_truncated_content_fallback(self):
        """When JSON content appears truncated, falls back to raw HTML."""
        proc, _ = self._make_processor(use_json=True)
        long_raw = "<p>" + "x" * 1000 + "</p>"
        short_json_content = "<p>ab</p>"
        json_data = {
            "title": "T",
            "author": "A",
            "text": "t",
            "content": short_json_content,
            "media_files": [],
        }
        full_result = {
            "metadata": {},
            "html": long_raw,
            "markdown": "md",
        }
        await proc._process_json_extraction(json_data, full_result)
        # Content should come from raw HTML since truncation was detected
        assert proc._data["content"]  # not empty

    @pytest.mark.asyncio
    async def test_process_json_extraction_empty_content_fallback(self):
        """When JSON content is empty, falls back to raw HTML."""
        proc, _ = self._make_processor(use_json=True)
        json_data = {
            "title": "T",
            "author": "A",
            "text": "t",
            "content": "",
            "media_files": [],
        }
        full_result = {
            "metadata": {},
            "html": "<p>raw</p>",
            "markdown": "md",
        }
        await proc._process_json_extraction(json_data, full_result)
        assert proc._data["content"]

    @pytest.mark.asyncio
    async def test_process_json_extraction_empty_content_no_raw_html(self):
        """When both JSON content and raw HTML are empty."""
        proc, _ = self._make_processor(use_json=True)
        json_data = {
            "title": "",
            "author": "",
            "text": "",
            "content": "",
            "media_files": [],
        }
        full_result = {
            "metadata": {},
            "html": "",
            "markdown": "",
        }
        await proc._process_json_extraction(json_data, full_result)
        assert proc._data["title"] == proc.url

    @pytest.mark.asyncio
    async def test_process_json_extraction_author_url_fallback(self):
        """When json_data has no author_url, falls back to url_parser."""
        proc, _ = self._make_processor(use_json=True)
        json_data = {
            "title": "T",
            "author": "A",
            "author_url": None,
            "text": "t",
            "content": "<p>" + "a" * 500 + "</p>",
            "media_files": [],
        }
        full_result = {
            "metadata": {},
            "html": "<p>" + "a" * 500 + "</p>",
            "markdown": "md",
        }
        await proc._process_json_extraction(json_data, full_result)
        assert proc._data["author_url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_process_json_extraction_text_truncation(self):
        proc, _ = self._make_processor(use_json=True)
        long_text = "x" * 600
        json_data = {
            "title": "T",
            "author": "A",
            "text": long_text,
            "content": "<p>" + "a" * 500 + "</p>",
            "media_files": [],
        }
        full_result = {
            "metadata": {},
            "html": "<p>" + "a" * 500 + "</p>",
            "markdown": "md",
        }
        await proc._process_json_extraction(json_data, full_result)
        assert len(proc._data["text"]) == 500

    @pytest.mark.asyncio
    async def test_process_json_extraction_empty_text(self):
        proc, _ = self._make_processor(use_json=True)
        json_data = {
            "title": "T",
            "author": "A",
            "text": "",
            "content": "<p>" + "a" * 500 + "</p>",
            "media_files": [],
        }
        full_result = {
            "metadata": {},
            "html": "<p>" + "a" * 500 + "</p>",
            "markdown": "md",
        }
        await proc._process_json_extraction(json_data, full_result)
        assert proc._data["text"] == ""

    @pytest.mark.asyncio
    async def test_process_json_extraction_og_image_key(self):
        """Test og_image fallback via 'og_image' key (not 'ogImage')."""
        proc, _ = self._make_processor(use_json=True)
        json_data = {
            "title": "T",
            "author": "A",
            "text": "t",
            "content": "<p>" + "a" * 500 + "</p>",
            "media_files": [],
        }
        full_result = {
            "metadata": {"og_image": "https://og2.com/img.png"},
            "html": "<p>" + "a" * 500 + "</p>",
            "markdown": "md",
        }
        await proc._process_json_extraction(json_data, full_result)
        assert len(proc._data["media_files"]) == 1

    @pytest.mark.asyncio
    async def test_json_extraction_non_dict_falls_back(self):
        """When json is not a dict, falls back to legacy processing."""
        proc, mock_client = self._make_processor(use_json=True)
        mock_client.scrape_url = AsyncMock(return_value={
            "json": "not a dict",
            "metadata": {"title": "T"},
            "markdown": "md",
            "html": "<p>html</p>",
        })
        with patch.object(proc, "_build_item_data", new_callable=AsyncMock):
            await proc._get_page_content()


# ---------------------------------------------------------------------------
# FirecrawlScraper
# ---------------------------------------------------------------------------


class TestFirecrawlScraper:
    @pytest.mark.asyncio
    @patch(
        "fastfetchbot_shared.services.scrapers.general.firecrawl_client.FirecrawlClient.get_instance"
    )
    async def test_get_processor_by_url(self, mock_gi):
        mock_gi.return_value = MagicMock()
        from fastfetchbot_shared.services.scrapers.general.firecrawl import FirecrawlScraper, FirecrawlDataProcessor
        scraper = FirecrawlScraper()
        processor = await scraper.get_processor_by_url("https://example.com/page")
        assert isinstance(processor, FirecrawlDataProcessor)
        assert processor.url == "https://example.com/page"

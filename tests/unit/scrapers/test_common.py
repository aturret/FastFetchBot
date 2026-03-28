"""Tests for packages/shared/fastfetchbot_shared/services/scrapers/common.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.models.url_metadata import UrlMetadata
from fastfetchbot_shared.services.scrapers.common import InfoExtractService
from fastfetchbot_shared.exceptions import ScraperError


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInfoExtractServiceInit:
    def test_init_sets_all_fields(self, make_url_metadata):
        url_metadata = make_url_metadata(
            source="twitter",
            url="https://twitter.com/user/status/123",
            content_type="post",
        )
        svc = InfoExtractService(
            url_metadata=url_metadata,
            data={"key": "val"},
            store_database=True,
            store_telegraph=False,
            store_document=True,
            extra_kwarg="extra",
        )
        assert svc.url == "https://twitter.com/user/status/123"
        assert svc.content_type == "post"
        assert svc.source == "twitter"
        assert svc.data == {"key": "val"}
        assert svc.store_database is True
        assert svc.store_telegraph is False
        assert svc.store_document is True
        assert svc.kwargs == {"extra_kwarg": "extra"}

    def test_init_defaults(self, make_url_metadata):
        url_metadata = make_url_metadata()
        svc = InfoExtractService(url_metadata=url_metadata)
        assert svc.data is None
        assert svc.store_database is False
        assert svc.store_telegraph is True
        assert svc.store_document is False
        assert svc.kwargs == {}


# ---------------------------------------------------------------------------
# category property
# ---------------------------------------------------------------------------

class TestCategory:
    def test_category_returns_source(self, make_url_metadata):
        url_metadata = make_url_metadata(source="reddit")
        svc = InfoExtractService(url_metadata=url_metadata)
        assert svc.category == "reddit"


# ---------------------------------------------------------------------------
# get_item with pre-existing metadata_item (skips scraping)
# ---------------------------------------------------------------------------

class TestGetItemWithExistingMetadata:
    @pytest.mark.asyncio
    async def test_get_item_with_metadata_skips_scraping(
        self, make_url_metadata, sample_metadata_item_dict
    ):
        svc = InfoExtractService(url_metadata=make_url_metadata())
        result = await svc.get_item(metadata_item=sample_metadata_item_dict)
        assert result["title"] == "Test Title"

    @pytest.mark.asyncio
    async def test_get_item_with_metadata_strips_title(self, make_url_metadata):
        svc = InfoExtractService(url_metadata=make_url_metadata())
        item = {"title": "  padded title  ", "url": "https://example.com"}
        result = await svc.get_item(metadata_item=item)
        assert result["title"] == "padded title"


# ---------------------------------------------------------------------------
# get_item with category in service_classes (e.g. "twitter")
# ---------------------------------------------------------------------------

class TestGetItemServiceClasses:
    @pytest.mark.asyncio
    async def test_get_item_twitter_category(self, make_url_metadata):
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.get_item = AsyncMock(
            return_value={"title": "  Twitter Post  ", "content": "hello"}
        )
        mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

        svc = InfoExtractService(
            url_metadata=make_url_metadata(source="twitter", url="https://twitter.com/x/1"),
            data={"some": "data"},
        )

        with patch.dict(svc.service_classes, {"twitter": mock_scraper_class}):
            result = await svc.get_item()

        mock_scraper_class.assert_called_once_with(
            url="https://twitter.com/x/1", category="twitter", data={"some": "data"}
        )
        mock_scraper_instance.get_item.assert_awaited_once()
        assert result["title"] == "Twitter Post"

    @pytest.mark.asyncio
    async def test_get_item_zhihu_category(self, make_url_metadata):
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.get_item = AsyncMock(
            return_value={"title": "Zhihu Answer", "content": "answer"}
        )
        mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

        svc = InfoExtractService(
            url_metadata=make_url_metadata(source="zhihu"),
        )

        with patch.dict(svc.service_classes, {"zhihu": mock_scraper_class}):
            result = await svc.get_item()

        assert result["title"] == "Zhihu Answer"


# ---------------------------------------------------------------------------
# get_item with ScraperManager categories
# ---------------------------------------------------------------------------

class TestGetItemScraperManager:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("category", ["bluesky", "weibo", "other", "unknown"])
    async def test_get_item_scraper_manager_categories(
        self, make_url_metadata, category
    ):
        mock_processor = MagicMock()
        mock_processor.get_item = AsyncMock(
            return_value={"title": f"  {category} item  "}
        )

        mock_scraper = MagicMock()
        mock_scraper.get_processor_by_url = AsyncMock(return_value=mock_processor)

        with patch(
            "fastfetchbot_shared.services.scrapers.common.ScraperManager"
        ) as MockSM:
            MockSM.init_scraper = AsyncMock()
            MockSM.scrapers = {category: mock_scraper}

            svc = InfoExtractService(
                url_metadata=make_url_metadata(
                    source=category, url="https://example.com/post"
                ),
            )
            result = await svc.get_item()

        MockSM.init_scraper.assert_awaited_once_with(category)
        mock_scraper.get_processor_by_url.assert_awaited_once_with(
            url="https://example.com/post"
        )
        mock_processor.get_item.assert_awaited_once()
        assert result["title"] == f"{category} item"


# ---------------------------------------------------------------------------
# get_item exception re-raise
# ---------------------------------------------------------------------------

class TestGetItemException:
    @pytest.mark.asyncio
    async def test_get_item_exception_reraises(self, make_url_metadata):
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.get_item = AsyncMock(
            side_effect=RuntimeError("scraper failed")
        )
        mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

        svc = InfoExtractService(
            url_metadata=make_url_metadata(source="twitter"),
        )

        with patch.dict(svc.service_classes, {"twitter": mock_scraper_class}):
            with pytest.raises(RuntimeError, match="scraper failed"):
                await svc.get_item()

    @pytest.mark.asyncio
    async def test_get_item_scraper_manager_exception_reraises(self, make_url_metadata):
        with patch(
            "fastfetchbot_shared.services.scrapers.common.ScraperManager"
        ) as MockSM:
            MockSM.init_scraper = AsyncMock(
                side_effect=ValueError("init failed")
            )

            svc = InfoExtractService(
                url_metadata=make_url_metadata(source="bluesky"),
            )
            with pytest.raises(ValueError, match="init failed"):
                await svc.get_item()


# ---------------------------------------------------------------------------
# process_item
# ---------------------------------------------------------------------------

class TestProcessItem:
    @pytest.mark.asyncio
    async def test_process_item_strips_title(self, make_url_metadata):
        svc = InfoExtractService(url_metadata=make_url_metadata())
        result = await svc.process_item({"title": "  hello world  "})
        assert result["title"] == "hello world"

    @pytest.mark.asyncio
    async def test_process_item_no_strip_needed(self, make_url_metadata):
        svc = InfoExtractService(url_metadata=make_url_metadata())
        result = await svc.process_item({"title": "clean"})
        assert result["title"] == "clean"


# ---------------------------------------------------------------------------
# _resolve_scraper_class
# ---------------------------------------------------------------------------

class TestResolveScraperClass:
    def test_known_category_returns_class(self, make_url_metadata):
        svc = InfoExtractService(url_metadata=make_url_metadata(source="twitter"))
        cls = svc._resolve_scraper_class("twitter")
        assert cls is not None

    def test_unknown_category_raises_scraper_error(self, make_url_metadata):
        svc = InfoExtractService(url_metadata=make_url_metadata())
        with pytest.raises(ScraperError, match="No scraper registered"):
            svc._resolve_scraper_class("tiktok")

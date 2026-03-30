"""Tests for cache lookup logic in InfoExtractService.get_item().

Covers the database_cache_ttl parameter and cache hit/miss/error paths.
Separated from test_common.py for clarity.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.models.url_metadata import UrlMetadata
from fastfetchbot_shared.services.scrapers.common import InfoExtractService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_service():
    """Factory for creating an InfoExtractService with cache-relevant params."""

    def _make(
        url="https://example.com/post/1",
        source="twitter",
        store_database=True,
        database_cache_ttl=3600,
        **kwargs,
    ):
        url_metadata = UrlMetadata(url=url, source=source, content_type="social_media")
        return InfoExtractService(
            url_metadata=url_metadata,
            store_database=store_database,
            database_cache_ttl=database_cache_ttl,
            **kwargs,
        )

    return _make


# ---------------------------------------------------------------------------
# database_cache_ttl init
# ---------------------------------------------------------------------------


class TestDatabaseCacheTtlInit:
    def test_default_database_cache_ttl_is_negative_one(self):
        url_metadata = UrlMetadata(url="https://x.com", source="twitter", content_type="social_media")
        svc = InfoExtractService(url_metadata=url_metadata)
        assert svc.database_cache_ttl == -1

    def test_custom_database_cache_ttl(self, make_service):
        svc = make_service(database_cache_ttl=86400)
        assert svc.database_cache_ttl == 86400


# ---------------------------------------------------------------------------
# Cache lookup in get_item
# ---------------------------------------------------------------------------


class TestGetItemCacheLookup:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self, make_service):
        """When cache has a valid entry, return it with _cached=True."""
        mock_cached_doc = MagicMock()
        mock_cached_doc.model_dump.return_value = {
            "title": "Cached Title",
            "url": "https://example.com/post/1",
            "media_files": [],
        }

        svc = make_service(store_database=True, database_cache_ttl=3600)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.find_cached",
            new_callable=AsyncMock,
            return_value=mock_cached_doc,
        ):
            result = await svc.get_item()

        assert result["_cached"] is True
        assert result["title"] == "Cached Title"
        mock_cached_doc.model_dump.assert_called_once_with(
            mode="json", exclude={"id"}
        )

    @pytest.mark.asyncio
    async def test_cache_miss_proceeds_to_scrape(self, make_service):
        """When cache returns None, fall through to actual scraping."""
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.get_item = AsyncMock(
            return_value={"title": "  Fresh Title  ", "content": "hi"}
        )
        mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

        svc = make_service(store_database=True, database_cache_ttl=3600)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.find_cached",
            new_callable=AsyncMock,
            return_value=None,
        ), patch.dict(svc.service_classes, {"twitter": mock_scraper_class}):
            result = await svc.get_item()

        assert "_cached" not in result
        assert result["title"] == "Fresh Title"
        mock_scraper_instance.get_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_error_proceeds_to_scrape(self, make_service):
        """When cache lookup raises, log error and proceed with scraping."""
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.get_item = AsyncMock(
            return_value={"title": "  Fallback  ", "content": "ok"}
        )
        mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

        svc = make_service(store_database=True, database_cache_ttl=3600)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.find_cached",
            new_callable=AsyncMock,
            side_effect=RuntimeError("MongoDB down"),
        ), patch.dict(svc.service_classes, {"twitter": mock_scraper_class}):
            result = await svc.get_item()

        assert result["title"] == "Fallback"
        mock_scraper_instance.get_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_skipped_when_store_database_false(self, make_service):
        """Cache lookup should be skipped entirely when store_database=False."""
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.get_item = AsyncMock(
            return_value={"title": "  No Cache  ", "content": "data"}
        )
        mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

        svc = make_service(store_database=False, database_cache_ttl=3600)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.find_cached",
            new_callable=AsyncMock,
        ) as mock_find_cached, patch.dict(
            svc.service_classes, {"twitter": mock_scraper_class}
        ):
            result = await svc.get_item()

        mock_find_cached.assert_not_awaited()
        assert result["title"] == "No Cache"

    @pytest.mark.asyncio
    async def test_cache_skipped_when_ttl_negative(self, make_service):
        """Cache lookup should be skipped when database_cache_ttl < 0."""
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.get_item = AsyncMock(
            return_value={"title": "  Force Refresh  ", "content": "data"}
        )
        mock_scraper_class = MagicMock(return_value=mock_scraper_instance)

        svc = make_service(store_database=True, database_cache_ttl=-1)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.find_cached",
            new_callable=AsyncMock,
        ) as mock_find_cached, patch.dict(
            svc.service_classes, {"twitter": mock_scraper_class}
        ):
            result = await svc.get_item()

        mock_find_cached.assert_not_awaited()
        assert result["title"] == "Force Refresh"

    @pytest.mark.asyncio
    async def test_cache_ttl_zero_passes_to_find_cached(self, make_service):
        """TTL=0 means 'never expire', should still call find_cached with ttl=0."""
        mock_cached_doc = MagicMock()
        mock_cached_doc.model_dump.return_value = {
            "title": "Never Expired",
            "url": "https://example.com/post/1",
        }

        svc = make_service(store_database=True, database_cache_ttl=0)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.find_cached",
            new_callable=AsyncMock,
            return_value=mock_cached_doc,
        ) as mock_find_cached:
            result = await svc.get_item()

        mock_find_cached.assert_awaited_once_with(
            "https://example.com/post/1", 0
        )
        assert result["_cached"] is True

"""Tests for MongoDB persistence in enrichment.enrich().

Covers: store_database parameter, save_metadata call, error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from async_worker.services.enrichment import enrich


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_metadata_item():
    """Minimal metadata item dict for enrichment."""
    return {
        "title": "  Test Title  ",
        "content": "<p>Test content</p>",
        "telegraph_url": "https://existing.url",
        "media_files": [],
        "message_type": "short",
    }


# ---------------------------------------------------------------------------
# store_database
# ---------------------------------------------------------------------------


class TestEnrichStoreDatabase:
    @pytest.mark.asyncio
    async def test_saves_to_mongodb_when_store_database_true(
        self, base_metadata_item
    ):
        with patch(
            "fastfetchbot_shared.database.mongodb.cache.save_metadata",
            new_callable=AsyncMock,
        ) as mock_save:
            result = await enrich(
                base_metadata_item,
                store_telegraph=False,
                store_document=False,
                store_database=True,
            )

        mock_save.assert_awaited_once_with(base_metadata_item)

    @pytest.mark.asyncio
    async def test_skips_mongodb_when_store_database_false(
        self, base_metadata_item
    ):
        with patch(
            "fastfetchbot_shared.database.mongodb.cache.save_metadata",
            new_callable=AsyncMock,
        ) as mock_save:
            await enrich(
                base_metadata_item,
                store_telegraph=False,
                store_document=False,
                store_database=False,
            )

        mock_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mongodb_error_does_not_crash(self, base_metadata_item):
        with patch(
            "fastfetchbot_shared.database.mongodb.cache.save_metadata",
            new_callable=AsyncMock,
            side_effect=RuntimeError("MongoDB connection failed"),
        ):
            # Should not raise
            result = await enrich(
                base_metadata_item,
                store_telegraph=False,
                store_document=False,
                store_database=True,
            )

        assert result["title"] == "Test Title"

    @pytest.mark.asyncio
    async def test_store_database_defaults_to_settings(self, base_metadata_item):
        """When store_database is None, it should use settings.DATABASE_ON."""
        from async_worker.config import settings as aw_settings

        with patch.object(aw_settings, "DATABASE_ON", True), \
             patch(
                 "fastfetchbot_shared.database.mongodb.cache.save_metadata",
                 new_callable=AsyncMock,
             ) as mock_save:
            await enrich(
                base_metadata_item,
                store_telegraph=False,
                store_document=False,
                store_database=None,  # should fall back to settings.DATABASE_ON
            )

        mock_save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_database_defaults_false_from_settings(
        self, base_metadata_item
    ):
        from async_worker.config import settings as aw_settings

        with patch.object(aw_settings, "DATABASE_ON", False), \
             patch(
                 "fastfetchbot_shared.database.mongodb.cache.save_metadata",
                 new_callable=AsyncMock,
             ) as mock_save:
            await enrich(
                base_metadata_item,
                store_telegraph=False,
                store_document=False,
                store_database=None,
            )

        mock_save.assert_not_awaited()

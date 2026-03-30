"""Tests for cache-related behavior in scrape_and_enrich task.

Covers: force_refresh_cache parameter, _cached flag handling, database_cache_ttl passthrough.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from async_worker.tasks.scrape import scrape_and_enrich


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    """ARQ worker context dict."""
    return {"redis": MagicMock()}


@pytest.fixture
def mock_outbox():
    """Patch outbox.push in the scrape module."""
    with patch("async_worker.tasks.scrape.outbox") as mock_mod:
        mock_mod.push = AsyncMock()
        yield mock_mod


@pytest.fixture
def mock_enrichment():
    """Patch enrichment.enrich in the scrape module."""
    with patch("async_worker.tasks.scrape.enrichment") as mock_mod:
        mock_mod.enrich = AsyncMock(
            return_value={
                "title": "Enriched",
                "content": "<p>hi</p>",
                "media_files": [],
                "telegraph_url": "https://telegra.ph/test",
            }
        )
        yield mock_mod


# ---------------------------------------------------------------------------
# force_refresh_cache → database_cache_ttl
# ---------------------------------------------------------------------------


class TestForceRefreshCache:
    @pytest.mark.asyncio
    async def test_force_refresh_sets_ttl_negative_one(
        self, ctx, mock_outbox, mock_enrichment
    ):
        """When force_refresh_cache=True, database_cache_ttl should be -1."""
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls:
            instance = AsyncMock()
            instance.get_item = AsyncMock(
                return_value={"title": "Test", "content": "", "media_files": []}
            )
            MockCls.return_value = instance

            await scrape_and_enrich(
                ctx,
                url="https://example.com",
                chat_id=1,
                force_refresh_cache=True,
            )

            call_kwargs = MockCls.call_args.kwargs
            assert call_kwargs["database_cache_ttl"] == -1

    @pytest.mark.asyncio
    async def test_no_force_refresh_uses_config_ttl(
        self, ctx, mock_outbox, mock_enrichment
    ):
        """When force_refresh_cache=False, use settings.DATABASE_CACHE_TTL."""
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls, \
             patch("async_worker.tasks.scrape.settings") as mock_settings:
            mock_settings.DATABASE_ON = True
            mock_settings.DATABASE_CACHE_TTL = 86400
            mock_settings.DOWNLOAD_VIDEO_TIMEOUT = 60

            instance = AsyncMock()
            instance.get_item = AsyncMock(
                return_value={"title": "Test", "content": "", "media_files": []}
            )
            MockCls.return_value = instance

            await scrape_and_enrich(
                ctx,
                url="https://example.com",
                chat_id=1,
                force_refresh_cache=False,
            )

            call_kwargs = MockCls.call_args.kwargs
            assert call_kwargs["database_cache_ttl"] == 86400

    @pytest.mark.asyncio
    async def test_default_force_refresh_is_false(
        self, ctx, mock_outbox, mock_enrichment
    ):
        """force_refresh_cache defaults to False."""
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls, \
             patch("async_worker.tasks.scrape.settings") as mock_settings:
            mock_settings.DATABASE_ON = True
            mock_settings.DATABASE_CACHE_TTL = 3600
            mock_settings.DOWNLOAD_VIDEO_TIMEOUT = 60

            instance = AsyncMock()
            instance.get_item = AsyncMock(
                return_value={"title": "Test", "content": "", "media_files": []}
            )
            MockCls.return_value = instance

            await scrape_and_enrich(
                ctx,
                url="https://example.com",
                chat_id=1,
                # force_refresh_cache not passed
            )

            call_kwargs = MockCls.call_args.kwargs
            assert call_kwargs["database_cache_ttl"] == 3600


# ---------------------------------------------------------------------------
# _cached flag → skip enrichment
# ---------------------------------------------------------------------------


class TestCachedFlagHandling:
    @pytest.mark.asyncio
    async def test_cached_result_skips_enrichment(
        self, ctx, mock_outbox
    ):
        """When get_item returns _cached=True, enrichment should NOT be called."""
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls, \
             patch("async_worker.tasks.scrape.enrichment") as mock_enrich:
            instance = AsyncMock()
            instance.get_item = AsyncMock(
                return_value={
                    "title": "Cached",
                    "content": "",
                    "media_files": [],
                    "_cached": True,
                }
            )
            MockCls.return_value = instance
            mock_enrich.enrich = AsyncMock()

            result = await scrape_and_enrich(
                ctx, url="https://example.com", chat_id=1
            )

        mock_enrich.enrich.assert_not_awaited()
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_cached_flag_popped_from_result(
        self, ctx, mock_outbox
    ):
        """The _cached flag should be popped (removed) from the metadata_item."""
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls, \
             patch("async_worker.tasks.scrape.enrichment") as mock_enrich:
            metadata = {
                "title": "Cached",
                "content": "",
                "media_files": [],
                "_cached": True,
            }
            instance = AsyncMock()
            instance.get_item = AsyncMock(return_value=metadata)
            MockCls.return_value = instance
            mock_enrich.enrich = AsyncMock()

            await scrape_and_enrich(
                ctx, url="https://example.com", chat_id=1
            )

        # The outbox should receive metadata without _cached
        outbox_call_kwargs = mock_outbox.push.call_args.kwargs
        pushed_item = outbox_call_kwargs["metadata_item"]
        assert "_cached" not in pushed_item

    @pytest.mark.asyncio
    async def test_non_cached_result_runs_enrichment(
        self, ctx, mock_outbox, mock_enrichment
    ):
        """When _cached is not in result, enrichment should be called."""
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls:
            instance = AsyncMock()
            instance.get_item = AsyncMock(
                return_value={
                    "title": "Fresh",
                    "content": "",
                    "media_files": [],
                }
            )
            MockCls.return_value = instance

            await scrape_and_enrich(
                ctx, url="https://example.com", chat_id=1
            )

        mock_enrichment.enrich.assert_awaited_once()

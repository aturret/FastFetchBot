"""Tests for apps/async-worker/async_worker/tasks/scrape.py"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

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
def mock_info_extract():
    """Patch InfoExtractService in the scrape module."""
    with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls:
        instance = AsyncMock()
        instance.get_item = AsyncMock(
            return_value={"title": "Test", "content": "<p>hi</p>", "media_files": []}
        )
        MockCls.return_value = instance
        yield MockCls, instance


@pytest.fixture
def mock_enrichment():
    """Patch enrichment.enrich in the scrape module."""
    with patch("async_worker.tasks.scrape.enrichment") as mock_mod:
        mock_mod.enrich = AsyncMock(
            return_value={
                "title": "Test",
                "content": "<p>hi</p>",
                "media_files": [],
                "telegraph_url": "https://telegra.ph/test",
            }
        )
        yield mock_mod


@pytest.fixture
def mock_outbox():
    """Patch outbox.push in the scrape module."""
    with patch("async_worker.tasks.scrape.outbox") as mock_mod:
        mock_mod.push = AsyncMock()
        yield mock_mod


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestScrapeAndEnrichSuccess:
    @pytest.mark.asyncio
    async def test_returns_success(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        result = await scrape_and_enrich(
            ctx,
            url="https://twitter.com/user/status/1",
            chat_id=12345,
            source="twitter",
            content_type="social_media",
        )
        assert result["status"] == "success"
        assert "job_id" in result

    @pytest.mark.asyncio
    async def test_generates_job_id_when_not_provided(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        result = await scrape_and_enrich(ctx, url="u", chat_id=1)
        # Should be a valid UUID
        uuid.UUID(result["job_id"])

    @pytest.mark.asyncio
    async def test_uses_provided_job_id(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        result = await scrape_and_enrich(
            ctx, url="u", chat_id=1, job_id="my-custom-id"
        )
        assert result["job_id"] == "my-custom-id"

    @pytest.mark.asyncio
    async def test_creates_url_metadata(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        MockCls, _ = mock_info_extract
        await scrape_and_enrich(
            ctx,
            url="https://example.com",
            chat_id=1,
            source="reddit",
            content_type="post",
        )
        call_kwargs = MockCls.call_args.kwargs
        url_metadata = call_kwargs["url_metadata"]
        assert url_metadata.url == "https://example.com"
        assert url_metadata.source == "reddit"
        assert url_metadata.content_type == "post"

    @pytest.mark.asyncio
    async def test_passes_celery_app_and_timeout(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        MockCls, _ = mock_info_extract
        await scrape_and_enrich(ctx, url="u", chat_id=1)
        call_kwargs = MockCls.call_args.kwargs
        assert "celery_app" in call_kwargs
        assert "timeout" in call_kwargs

    @pytest.mark.asyncio
    async def test_disables_telegraph_and_document_for_scraping(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        """Scraping step should not do enrichment — that's handled separately."""
        MockCls, _ = mock_info_extract
        await scrape_and_enrich(ctx, url="u", chat_id=1)
        call_kwargs = MockCls.call_args.kwargs
        assert call_kwargs["store_telegraph"] is False
        assert call_kwargs["store_document"] is False

    @pytest.mark.asyncio
    async def test_passes_enrichment_flags(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        await scrape_and_enrich(
            ctx, url="u", chat_id=1, store_telegraph=True, store_document=True
        )
        mock_enrichment.enrich.assert_awaited_once()
        call_kwargs = mock_enrichment.enrich.call_args.kwargs
        assert call_kwargs["store_telegraph"] is True
        assert call_kwargs["store_document"] is True

    @pytest.mark.asyncio
    async def test_pushes_result_to_outbox(
        self, ctx, mock_info_extract, mock_enrichment, mock_outbox
    ):
        await scrape_and_enrich(
            ctx,
            url="u",
            chat_id=42,
            job_id="j1",
            message_id=99,
        )
        mock_outbox.push.assert_awaited_once()
        call_kwargs = mock_outbox.push.call_args.kwargs
        assert call_kwargs["job_id"] == "j1"
        assert call_kwargs["chat_id"] == 42
        assert call_kwargs["message_id"] == 99
        assert call_kwargs["metadata_item"] is not None


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------


class TestScrapeAndEnrichError:
    @pytest.mark.asyncio
    async def test_scraping_failure_pushes_error(
        self, ctx, mock_enrichment, mock_outbox
    ):
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls:
            instance = AsyncMock()
            instance.get_item = AsyncMock(side_effect=RuntimeError("scrape boom"))
            MockCls.return_value = instance

            result = await scrape_and_enrich(
                ctx, url="u", chat_id=1, job_id="j-err"
            )

        assert result["status"] == "error"
        assert "scrape boom" in result["error"]
        mock_outbox.push.assert_awaited_once()
        assert mock_outbox.push.call_args.kwargs["error"] == "scrape boom"

    @pytest.mark.asyncio
    async def test_enrichment_failure_pushes_error(
        self, ctx, mock_info_extract, mock_outbox
    ):
        with patch("async_worker.tasks.scrape.enrichment") as mock_enrich:
            mock_enrich.enrich = AsyncMock(
                side_effect=ValueError("enrich failed")
            )
            result = await scrape_and_enrich(
                ctx, url="u", chat_id=1, job_id="j-err2"
            )

        assert result["status"] == "error"
        assert "enrich failed" in result["error"]
        mock_outbox.push.assert_awaited_once()
        assert mock_outbox.push.call_args.kwargs["error"] == "enrich failed"

    @pytest.mark.asyncio
    async def test_error_includes_chat_id_in_outbox(
        self, ctx, mock_enrichment, mock_outbox
    ):
        with patch("async_worker.tasks.scrape.InfoExtractService") as MockCls:
            instance = AsyncMock()
            instance.get_item = AsyncMock(side_effect=RuntimeError("fail"))
            MockCls.return_value = instance

            await scrape_and_enrich(ctx, url="u", chat_id=99999)

        assert mock_outbox.push.call_args.kwargs["chat_id"] == 99999

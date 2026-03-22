"""Tests for apps/async-worker/async_worker/services/enrichment.py"""

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
        "telegraph_url": "",
        "media_files": [],
        "message_type": "short",
    }


@pytest.fixture
def mock_telegraph():
    """Patch Telegraph.from_dict and .get_telegraph."""
    with patch("async_worker.services.enrichment.Telegraph") as MockTg:
        instance = MagicMock()
        instance.get_telegraph = AsyncMock(return_value="https://telegra.ph/test-01")
        MockTg.from_dict.return_value = instance
        yield MockTg, instance


@pytest.fixture
def mock_pdf_export():
    """Patch PdfExport in the enrichment module."""
    with patch(
        "async_worker.services.enrichment.PdfExport", create=True
    ) as MockPdf:
        # The import is lazy, so we patch at the module level where it's imported
        yield MockPdf


# ---------------------------------------------------------------------------
# Telegraph enrichment
# ---------------------------------------------------------------------------


class TestTelegraphEnrichment:
    @pytest.mark.asyncio
    async def test_publishes_to_telegraph_when_enabled(
        self, base_metadata_item, mock_telegraph
    ):
        MockTg, instance = mock_telegraph
        result = await enrich(base_metadata_item, store_telegraph=True)

        MockTg.from_dict.assert_called_once_with(base_metadata_item)
        instance.get_telegraph.assert_awaited_once()
        assert result["telegraph_url"] == "https://telegra.ph/test-01"

    @pytest.mark.asyncio
    async def test_skips_telegraph_when_disabled(self, base_metadata_item, mock_telegraph):
        MockTg, instance = mock_telegraph
        result = await enrich(
            base_metadata_item, store_telegraph=False, store_document=False
        )

        MockTg.from_dict.assert_not_called()
        instance.get_telegraph.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_telegraph_failure_sets_empty_url(
        self, base_metadata_item, mock_telegraph
    ):
        _, instance = mock_telegraph
        instance.get_telegraph = AsyncMock(side_effect=RuntimeError("telegraph down"))

        result = await enrich(base_metadata_item, store_telegraph=True)
        assert result["telegraph_url"] == ""

    @pytest.mark.asyncio
    async def test_long_message_forces_telegraph(self, base_metadata_item, mock_telegraph):
        from fastfetchbot_shared.models.metadata_item import MessageType

        base_metadata_item["message_type"] = MessageType.LONG
        MockTg, instance = mock_telegraph

        result = await enrich(
            base_metadata_item, store_telegraph=False, store_document=False
        )

        # Should have been forced to True despite store_telegraph=False
        MockTg.from_dict.assert_called_once()
        instance.get_telegraph.assert_awaited_once()


# ---------------------------------------------------------------------------
# PDF enrichment
# ---------------------------------------------------------------------------


class TestPdfEnrichment:
    @pytest.mark.asyncio
    async def test_exports_pdf_when_store_document_true(self, base_metadata_item):
        with patch(
            "fastfetchbot_shared.services.file_export.pdf_export.PdfExport"
        ) as MockPdf:
            mock_instance = AsyncMock()
            mock_instance.export = AsyncMock(return_value="/tmp/test.pdf")
            MockPdf.return_value = mock_instance

            result = await enrich(
                base_metadata_item,
                store_telegraph=False,
                store_document=True,
            )

            assert any(
                f["url"] == "/tmp/test.pdf" for f in result["media_files"]
            )

    @pytest.mark.asyncio
    async def test_pdf_fallback_when_telegraph_fails(self, base_metadata_item, mock_telegraph):
        _, instance = mock_telegraph
        instance.get_telegraph = AsyncMock(side_effect=RuntimeError("fail"))

        with patch(
            "fastfetchbot_shared.services.file_export.pdf_export.PdfExport"
        ) as MockPdf:
            mock_pdf_instance = AsyncMock()
            mock_pdf_instance.export = AsyncMock(return_value="/tmp/fallback.pdf")
            MockPdf.return_value = mock_pdf_instance

            result = await enrich(
                base_metadata_item,
                store_telegraph=True,
                store_document=False,
            )

            # telegraph_url is "" so PDF should trigger as fallback
            assert result["telegraph_url"] == ""
            assert any(
                f["url"] == "/tmp/fallback.pdf" for f in result["media_files"]
            )

    @pytest.mark.asyncio
    async def test_pdf_failure_does_not_crash(self, base_metadata_item):
        with patch(
            "fastfetchbot_shared.services.file_export.pdf_export.PdfExport"
        ) as MockPdf:
            mock_instance = AsyncMock()
            mock_instance.export = AsyncMock(side_effect=RuntimeError("pdf boom"))
            MockPdf.return_value = mock_instance

            # Should not raise
            result = await enrich(
                base_metadata_item,
                store_telegraph=False,
                store_document=True,
            )
            assert result["media_files"] == []


# ---------------------------------------------------------------------------
# Title stripping
# ---------------------------------------------------------------------------


class TestTitleStripping:
    @pytest.mark.asyncio
    async def test_strips_title_whitespace(self, base_metadata_item):
        base_metadata_item["title"] = "  padded title  "
        result = await enrich(
            base_metadata_item, store_telegraph=False, store_document=False
        )
        assert result["title"] == "padded title"


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    @pytest.mark.asyncio
    async def test_uses_config_defaults_when_none(self, base_metadata_item, mock_telegraph):
        """When store_telegraph/store_document are None, config defaults should be used."""
        with patch("async_worker.services.enrichment.STORE_TELEGRAPH", True), \
             patch("async_worker.services.enrichment.STORE_DOCUMENT", False):
            result = await enrich(base_metadata_item)

        # STORE_TELEGRAPH=True means Telegraph should be called
        MockTg, instance = mock_telegraph
        MockTg.from_dict.assert_called_once()

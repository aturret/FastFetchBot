"""Tests for packages/shared/fastfetchbot_shared/database/mongodb/cache.py"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_metadata(url="https://example.com", version=1, timestamp=None):
    """Create a mock Metadata document."""
    doc = MagicMock()
    doc.url = url
    doc.version = version
    doc.timestamp = timestamp or datetime.utcnow()
    return doc


def _make_find_chain(result):
    """Build a mock chain for Metadata.find().sort().limit().first_or_none()."""
    mock_first = AsyncMock(return_value=result)
    mock_limit = MagicMock()
    mock_limit.first_or_none = mock_first
    mock_sort = MagicMock()
    mock_sort.limit.return_value = mock_limit
    mock_find = MagicMock()
    mock_find.sort.return_value = mock_sort
    return mock_find


# ---------------------------------------------------------------------------
# find_cached
# ---------------------------------------------------------------------------


class TestFindCached:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_document_found(self):
        mock_find = _make_find_chain(None)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.Metadata"
        ) as MockMetadata:
            MockMetadata.find.return_value = mock_find.sort.return_value.__class__()
            # Simpler approach: patch the full chain
            MockMetadata.find.return_value = mock_find

            from fastfetchbot_shared.database.mongodb.cache import find_cached

            result = await find_cached("https://example.com", ttl_seconds=3600)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_document_when_ttl_zero(self):
        """ttl_seconds=0 means never expire — always return cached doc."""
        doc = _make_mock_metadata(timestamp=datetime.utcnow() - timedelta(days=365))
        mock_find = _make_find_chain(doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.Metadata"
        ) as MockMetadata:
            MockMetadata.find.return_value = mock_find

            from fastfetchbot_shared.database.mongodb.cache import find_cached

            result = await find_cached("https://example.com", ttl_seconds=0)

        assert result is doc

    @pytest.mark.asyncio
    async def test_returns_document_within_ttl(self):
        doc = _make_mock_metadata(timestamp=datetime.utcnow() - timedelta(seconds=30))
        mock_find = _make_find_chain(doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.Metadata"
        ) as MockMetadata:
            MockMetadata.find.return_value = mock_find

            from fastfetchbot_shared.database.mongodb.cache import find_cached

            result = await find_cached("https://example.com", ttl_seconds=3600)

        assert result is doc

    @pytest.mark.asyncio
    async def test_returns_none_when_ttl_expired(self):
        doc = _make_mock_metadata(
            timestamp=datetime.utcnow() - timedelta(seconds=7200)
        )
        mock_find = _make_find_chain(doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.Metadata"
        ) as MockMetadata:
            MockMetadata.find.return_value = mock_find

            from fastfetchbot_shared.database.mongodb.cache import find_cached

            result = await find_cached("https://example.com", ttl_seconds=3600)

        assert result is None


# ---------------------------------------------------------------------------
# save_metadata
# ---------------------------------------------------------------------------


class TestSaveMetadata:
    @pytest.mark.asyncio
    async def test_first_save_uses_version_1(self):
        mock_find = _make_find_chain(None)  # No existing doc

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.Metadata"
        ) as MockMetadata:
            MockMetadata.find.return_value = mock_find
            mock_constructed = MagicMock()
            MockMetadata.model_construct.return_value = mock_constructed
            MockMetadata.insert = AsyncMock()

            from fastfetchbot_shared.database.mongodb.cache import save_metadata

            item = {"url": "https://example.com", "title": "Test"}
            result = await save_metadata(item)

        assert item["version"] == 1
        MockMetadata.model_construct.assert_called_once()
        MockMetadata.insert.assert_awaited_once_with(mock_constructed)
        assert result is mock_constructed

    @pytest.mark.asyncio
    async def test_increments_version_from_existing(self):
        existing_doc = _make_mock_metadata(version=3)
        mock_find = _make_find_chain(existing_doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.Metadata"
        ) as MockMetadata:
            MockMetadata.find.return_value = mock_find
            mock_constructed = MagicMock()
            MockMetadata.model_construct.return_value = mock_constructed
            MockMetadata.insert = AsyncMock()

            from fastfetchbot_shared.database.mongodb.cache import save_metadata

            item = {"url": "https://example.com", "title": "Test"}
            await save_metadata(item)

        assert item["version"] == 4

    @pytest.mark.asyncio
    async def test_uses_url_from_metadata_item(self):
        mock_find = _make_find_chain(None)

        with patch(
            "fastfetchbot_shared.database.mongodb.cache.Metadata"
        ) as MockMetadata:
            MockMetadata.find.return_value = mock_find
            MockMetadata.model_construct.return_value = MagicMock()
            MockMetadata.insert = AsyncMock()

            from fastfetchbot_shared.database.mongodb.cache import save_metadata

            item = {"url": "https://specific.com/path", "title": "Test"}
            await save_metadata(item)

        # Verify the find was called (to look up existing version)
        MockMetadata.find.assert_called()

    @pytest.mark.asyncio
    async def test_missing_url_raises_value_error(self):
        from fastfetchbot_shared.database.mongodb.cache import save_metadata

        with pytest.raises(ValueError, match="non-empty 'url'"):
            await save_metadata({"title": "No URL"})

    @pytest.mark.asyncio
    async def test_empty_url_raises_value_error(self):
        from fastfetchbot_shared.database.mongodb.cache import save_metadata

        with pytest.raises(ValueError, match="non-empty 'url'"):
            await save_metadata({"url": "", "title": "Empty URL"})

    @pytest.mark.asyncio
    async def test_whitespace_only_url_raises_value_error(self):
        from fastfetchbot_shared.database.mongodb.cache import save_metadata

        with pytest.raises(ValueError, match="non-empty 'url'"):
            await save_metadata({"url": "   ", "title": "Whitespace URL"})

"""Tests for apps/telegram-bot/core/services/user_settings.py

Covers: ensure_user_settings, get/toggle auto_fetch_in_dm, get/toggle force_refresh_cache.
All DB interactions are mocked via get_session.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_with_result(scalar_value):
    """Create a mock async session that returns scalar_value from execute().scalar_one_or_none()."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_value

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    return mock_get_session, mock_session


# ---------------------------------------------------------------------------
# ensure_user_settings
# ---------------------------------------------------------------------------


class TestEnsureUserSettings:
    @pytest.mark.asyncio
    async def test_creates_row_when_not_exists(self):
        mock_get_session, mock_session = _mock_session_with_result(None)

        with patch(
            "core.services.user_settings.get_session", mock_get_session
        ), patch("core.services.user_settings._known_user_ids", set()):
            from core.services.user_settings import ensure_user_settings

            await ensure_user_settings(12345)

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_db_when_user_already_known(self):
        mock_get_session, mock_session = _mock_session_with_result(None)

        with patch(
            "core.services.user_settings.get_session", mock_get_session
        ), patch("core.services.user_settings._known_user_ids", {12345}):
            from core.services.user_settings import ensure_user_settings

            await ensure_user_settings(12345)

        mock_session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_create_row_when_exists(self):
        existing_setting = MagicMock()
        mock_get_session, mock_session = _mock_session_with_result(existing_setting)

        with patch(
            "core.services.user_settings.get_session", mock_get_session
        ), patch("core.services.user_settings._known_user_ids", set()):
            from core.services.user_settings import ensure_user_settings

            await ensure_user_settings(99999)

        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_user_to_known_ids(self):
        mock_get_session, _ = _mock_session_with_result(MagicMock())
        known_ids = set()

        with patch(
            "core.services.user_settings.get_session", mock_get_session
        ), patch("core.services.user_settings._known_user_ids", known_ids):
            from core.services.user_settings import ensure_user_settings

            await ensure_user_settings(42)

        assert 42 in known_ids


# ---------------------------------------------------------------------------
# get_auto_fetch_in_dm
# ---------------------------------------------------------------------------


class TestGetAutoFetchInDm:
    @pytest.mark.asyncio
    async def test_returns_stored_value(self):
        mock_get_session, _ = _mock_session_with_result(False)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import get_auto_fetch_in_dm

            result = await get_auto_fetch_in_dm(1)

        assert result is False

    @pytest.mark.asyncio
    async def test_defaults_to_true_when_none(self):
        mock_get_session, _ = _mock_session_with_result(None)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import get_auto_fetch_in_dm

            result = await get_auto_fetch_in_dm(1)

        assert result is True


# ---------------------------------------------------------------------------
# toggle_auto_fetch_in_dm
# ---------------------------------------------------------------------------


class TestToggleAutoFetchInDm:
    @pytest.mark.asyncio
    async def test_toggles_existing_setting(self):
        existing = MagicMock()
        existing.auto_fetch_in_dm = True
        mock_get_session, _ = _mock_session_with_result(existing)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import toggle_auto_fetch_in_dm

            result = await toggle_auto_fetch_in_dm(1)

        assert existing.auto_fetch_in_dm is False
        assert result is False

    @pytest.mark.asyncio
    async def test_creates_setting_when_not_exists(self):
        mock_get_session, mock_session = _mock_session_with_result(None)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import toggle_auto_fetch_in_dm

            result = await toggle_auto_fetch_in_dm(1)

        # New setting created with auto_fetch=False (toggled from default True)
        mock_session.add.assert_called_once()
        assert result is False


# ---------------------------------------------------------------------------
# get_force_refresh_cache
# ---------------------------------------------------------------------------


class TestGetForceRefreshCache:
    @pytest.mark.asyncio
    async def test_returns_stored_value(self):
        mock_get_session, _ = _mock_session_with_result(True)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import get_force_refresh_cache

            result = await get_force_refresh_cache(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_defaults_to_false_when_none(self):
        mock_get_session, _ = _mock_session_with_result(None)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import get_force_refresh_cache

            result = await get_force_refresh_cache(1)

        assert result is False


# ---------------------------------------------------------------------------
# toggle_force_refresh_cache
# ---------------------------------------------------------------------------


class TestToggleForceRefreshCache:
    @pytest.mark.asyncio
    async def test_toggles_existing_setting(self):
        existing = MagicMock()
        existing.force_refresh_cache = False
        mock_get_session, _ = _mock_session_with_result(existing)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import toggle_force_refresh_cache

            result = await toggle_force_refresh_cache(1)

        assert existing.force_refresh_cache is True
        assert result is True

    @pytest.mark.asyncio
    async def test_creates_setting_when_not_exists(self):
        mock_get_session, mock_session = _mock_session_with_result(None)

        with patch("core.services.user_settings.get_session", mock_get_session):
            from core.services.user_settings import toggle_force_refresh_cache

            result = await toggle_force_refresh_cache(1)

        # New setting created with force_refresh=True (toggled from default False)
        mock_session.add.assert_called_once()
        assert result is True

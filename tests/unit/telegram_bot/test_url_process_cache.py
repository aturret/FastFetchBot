"""Tests for force_refresh_cache integration in url_process.py

Covers: https_url_process reads force_refresh preference and passes it through.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.handlers.url_process import (
    _auto_fetch_urls,
    _fetch_and_send,
)


# ---------------------------------------------------------------------------
# _fetch_and_send
# ---------------------------------------------------------------------------


class TestFetchAndSend:
    @pytest.mark.asyncio
    async def test_queue_mode_passes_force_refresh_kwarg(self):
        with patch("core.handlers.url_process.settings") as mock_settings, \
             patch(
                 "core.queue_client.enqueue_scrape",
                 new_callable=AsyncMock,
             ) as mock_enqueue:
            mock_settings.SCRAPE_MODE = "queue"

            await _fetch_and_send(
                url="https://example.com",
                chat_id=123,
                source="twitter",
                content_type="social_media",
                force_refresh_cache=True,
            )

        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["force_refresh_cache"] is True

    @pytest.mark.asyncio
    async def test_api_mode_passes_force_refresh_kwarg(self):
        import sys
        import importlib

        mock_api = MagicMock()
        mock_api.get_item = AsyncMock(
            return_value={"title": "Test", "media_files": []}
        )

        # Pre-inject the mock into sys.modules so `from core import api_client`
        # resolves to our mock instead of trying a real HTTP connection.
        # Also patch the attribute on the `core` package itself in case it was
        # already imported by a previous test.
        old_mod = sys.modules.get("core.api_client")
        sys.modules["core.api_client"] = mock_api

        import core
        old_attr = getattr(core, "api_client", None)
        core.api_client = mock_api
        try:
            with patch("core.handlers.url_process.settings") as mock_settings, \
                 patch(
                     "core.handlers.url_process.send_item_message",
                     new_callable=AsyncMock,
                 ):
                mock_settings.SCRAPE_MODE = "api"

                await _fetch_and_send(
                    url="https://example.com",
                    chat_id=123,
                    force_refresh_cache=True,
                )

            mock_api.get_item.assert_awaited_once()
            call_kwargs = mock_api.get_item.call_args.kwargs
            assert call_kwargs["force_refresh_cache"] is True
        finally:
            if old_mod is not None:
                sys.modules["core.api_client"] = old_mod
            else:
                sys.modules.pop("core.api_client", None)
            if old_attr is not None:
                core.api_client = old_attr
            elif hasattr(core, "api_client"):
                delattr(core, "api_client")


# ---------------------------------------------------------------------------
# _auto_fetch_urls
# ---------------------------------------------------------------------------


class TestAutoFetchUrls:
    @pytest.mark.asyncio
    async def test_passes_force_refresh_to_fetch_and_send(self):
        mock_message = MagicMock()
        mock_message.chat_id = 123
        mock_message.parse_entities.return_value = {
            MagicMock(): "https://twitter.com/user/status/1"
        }

        with patch(
            "core.handlers.url_process._get_url_metadata",
            new_callable=AsyncMock,
            return_value={
                "url": "https://twitter.com/user/status/1",
                "source": "twitter",
                "content_type": "social_media",
            },
        ), patch(
            "core.handlers.url_process._fetch_and_send",
            new_callable=AsyncMock,
        ) as mock_fetch, patch(
            "core.handlers.url_process.SOCIAL_MEDIA_WEBSITE_PATTERNS",
            {"twitter": None},
        ):
            await _auto_fetch_urls(mock_message, force_refresh_cache=True)

        mock_fetch.assert_awaited()
        # At least one call should have force_refresh_cache=True
        any_call_has_refresh = any(
            call.kwargs.get("force_refresh_cache") is True
            for call in mock_fetch.call_args_list
        )
        assert any_call_has_refresh

    @pytest.mark.asyncio
    async def test_force_refresh_defaults_to_false(self):
        mock_message = MagicMock()
        mock_message.chat_id = 123
        mock_message.parse_entities.return_value = {
            MagicMock(): "https://twitter.com/user/status/1"
        }

        with patch(
            "core.handlers.url_process._get_url_metadata",
            new_callable=AsyncMock,
            return_value={
                "url": "https://twitter.com/user/status/1",
                "source": "twitter",
                "content_type": "social_media",
            },
        ), patch(
            "core.handlers.url_process._fetch_and_send",
            new_callable=AsyncMock,
        ) as mock_fetch, patch(
            "core.handlers.url_process.SOCIAL_MEDIA_WEBSITE_PATTERNS",
            {"twitter": None},
        ):
            await _auto_fetch_urls(mock_message)  # default force_refresh_cache

        mock_fetch.assert_awaited()
        any_call_has_refresh = any(
            call.kwargs.get("force_refresh_cache") is True
            for call in mock_fetch.call_args_list
        )
        # Default is False, so no call should have force_refresh_cache=True
        assert not any_call_has_refresh

    @pytest.mark.asyncio
    async def test_skips_banned_urls(self):
        mock_message = MagicMock()
        mock_message.chat_id = 123
        mock_message.parse_entities.return_value = {
            MagicMock(): "https://banned.com/page"
        }

        with patch(
            "core.handlers.url_process._get_url_metadata",
            new_callable=AsyncMock,
            return_value={
                "url": "https://banned.com/page",
                "source": "banned",
                "content_type": "",
            },
        ), patch(
            "core.handlers.url_process._fetch_and_send",
            new_callable=AsyncMock,
        ) as mock_fetch, patch(
            "core.handlers.url_process.SOCIAL_MEDIA_WEBSITE_PATTERNS",
            {},
        ), patch(
            "core.handlers.url_process.VIDEO_WEBSITE_PATTERNS",
            {},
        ):
            await _auto_fetch_urls(mock_message, force_refresh_cache=True)

        mock_fetch.assert_not_awaited()

"""Tests for force_refresh_cache integration in buttons.py

Covers: buttons_process reads user's force_refresh_cache and adds to extra_args.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.handlers.buttons import buttons_process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_button_update(
    callback_data,
    user_id=12345,
    chat_id=67890,
):
    """Create a mock Update for button callback."""
    update = MagicMock()
    update.effective_user.id = user_id

    query = MagicMock()
    query.data = callback_data
    query.from_user.id = user_id
    query.answer = AsyncMock()
    query.message.chat_id = chat_id
    query.message.reply_text = AsyncMock(return_value=MagicMock(delete=AsyncMock()))
    query.message.delete = AsyncMock()
    update.callback_query = query

    return update


# ---------------------------------------------------------------------------
# force_refresh_cache in buttons_process
# ---------------------------------------------------------------------------


class TestButtonsForceRefreshCache:
    @pytest.mark.asyncio
    async def test_force_refresh_added_to_extra_args_in_queue_mode(self):
        data = {
            "type": "private",
            "url": "https://twitter.com/user/status/1",
            "source": "twitter",
            "content_type": "social_media",
            "extra_args": {},
        }
        update = _make_button_update(callback_data=data)
        context = MagicMock()
        context.drop_callback_data = MagicMock()

        with patch(
            "core.handlers.buttons.get_force_refresh_cache",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "core.handlers.buttons.settings"
        ) as mock_settings, patch(
            "core.queue_client.enqueue_scrape",
            new_callable=AsyncMock,
        ) as mock_enqueue, patch(
            "core.handlers.buttons.TELEGRAM_CHANNEL_ID", []
        ):
            mock_settings.SCRAPE_MODE = "queue"

            await buttons_process(update, context)

        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs.get("force_refresh_cache") is True

    @pytest.mark.asyncio
    async def test_force_refresh_not_added_when_false(self):
        data = {
            "type": "private",
            "url": "https://twitter.com/user/status/1",
            "source": "twitter",
            "content_type": "social_media",
            "extra_args": {},
        }
        update = _make_button_update(callback_data=data)
        context = MagicMock()
        context.drop_callback_data = MagicMock()

        with patch(
            "core.handlers.buttons.get_force_refresh_cache",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "core.handlers.buttons.settings"
        ) as mock_settings, patch(
            "core.queue_client.enqueue_scrape",
            new_callable=AsyncMock,
        ) as mock_enqueue, patch(
            "core.handlers.buttons.TELEGRAM_CHANNEL_ID", []
        ):
            mock_settings.SCRAPE_MODE = "queue"

            await buttons_process(update, context)

        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        assert "force_refresh_cache" not in call_kwargs

    @pytest.mark.asyncio
    async def test_cancel_button_does_not_check_force_refresh(self):
        data = {"type": "cancel"}
        update = _make_button_update(callback_data=data)
        context = MagicMock()
        context.drop_callback_data = MagicMock()

        with patch(
            "core.handlers.buttons.get_force_refresh_cache",
            new_callable=AsyncMock,
        ) as mock_get_refresh:
            await buttons_process(update, context)

        mock_get_refresh.assert_not_awaited()
        update.callback_query.answer.assert_awaited_once_with("Canceled")

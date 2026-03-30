"""Tests for apps/telegram-bot/core/handlers/commands.py

Covers: start_command, settings_command, settings_callback,
        _build_settings_keyboard, _build_settings_text.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.handlers.commands import (
    start_command,
    settings_command,
    settings_callback,
    _build_settings_keyboard,
    _build_settings_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update(user_id=12345):
    """Create a mock Update with effective_user and message."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    return update


def _make_callback_update(user_id=12345, callback_data="settings:close"):
    """Create a mock Update with callback_query."""
    update = MagicMock()
    update.effective_user.id = user_id
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = callback_data
    query.from_user.id = user_id
    query.message.delete = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


# ---------------------------------------------------------------------------
# _build_settings_keyboard
# ---------------------------------------------------------------------------


class TestBuildSettingsKeyboard:
    def test_auto_fetch_on_force_refresh_off(self):
        keyboard = _build_settings_keyboard(auto_fetch=True, force_refresh=False)
        assert len(keyboard) == 3  # auto_fetch row, force_refresh row, close row
        assert "ON" in keyboard[0][0].text
        assert "Auto-fetch" in keyboard[0][0].text
        assert "OFF" in keyboard[1][0].text
        assert "Force refresh" in keyboard[1][0].text
        assert keyboard[2][0].text == "Close"

    def test_auto_fetch_off_force_refresh_on(self):
        keyboard = _build_settings_keyboard(auto_fetch=False, force_refresh=True)
        assert "OFF" in keyboard[0][0].text
        assert "ON" in keyboard[1][0].text

    def test_callback_data_values(self):
        keyboard = _build_settings_keyboard(auto_fetch=True, force_refresh=False)
        assert keyboard[0][0].callback_data == "settings:toggle_auto_fetch"
        assert keyboard[1][0].callback_data == "settings:toggle_force_refresh"
        assert keyboard[2][0].callback_data == "settings:close"


# ---------------------------------------------------------------------------
# _build_settings_text
# ---------------------------------------------------------------------------


class TestBuildSettingsText:
    def test_both_enabled(self):
        text = _build_settings_text(auto_fetch=True, force_refresh=True)
        assert "Auto-fetch in DM: enabled" in text
        assert "Force refresh cache: enabled" in text

    def test_both_disabled(self):
        text = _build_settings_text(auto_fetch=False, force_refresh=False)
        assert "Auto-fetch in DM: disabled" in text
        assert "Force refresh cache: disabled" in text

    def test_contains_descriptions(self):
        text = _build_settings_text(auto_fetch=True, force_refresh=False)
        assert "automatically processed" in text
        assert "cached results are ignored" in text


# ---------------------------------------------------------------------------
# start_command
# ---------------------------------------------------------------------------


class TestStartCommand:
    @pytest.mark.asyncio
    async def test_ensures_user_settings(self):
        update = _make_update(user_id=42)
        context = MagicMock()

        with patch(
            "core.handlers.commands.ensure_user_settings",
            new_callable=AsyncMock,
        ) as mock_ensure:
            await start_command(update, context)

        mock_ensure.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_sends_welcome_message(self):
        update = _make_update()
        context = MagicMock()

        with patch(
            "core.handlers.commands.ensure_user_settings",
            new_callable=AsyncMock,
        ):
            await start_command(update, context)

        update.message.reply_text.assert_awaited_once()
        message_text = update.message.reply_text.call_args[0][0]
        assert "Welcome" in message_text
        assert "/settings" in message_text


# ---------------------------------------------------------------------------
# settings_command
# ---------------------------------------------------------------------------


class TestSettingsCommand:
    @pytest.mark.asyncio
    async def test_shows_settings_with_keyboard(self):
        update = _make_update(user_id=42)
        context = MagicMock()

        with patch(
            "core.handlers.commands.ensure_user_settings",
            new_callable=AsyncMock,
        ), patch(
            "core.handlers.commands.get_auto_fetch_in_dm",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "core.handlers.commands.get_force_refresh_cache",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await settings_command(update, context)

        update.message.reply_text.assert_awaited_once()
        call_kwargs = update.message.reply_text.call_args.kwargs
        assert "reply_markup" in call_kwargs
        assert "Auto-fetch in DM: enabled" in call_kwargs["text"]
        assert "Force refresh cache: disabled" in call_kwargs["text"]


# ---------------------------------------------------------------------------
# settings_callback
# ---------------------------------------------------------------------------


class TestSettingsCallback:
    @pytest.mark.asyncio
    async def test_close_deletes_message(self):
        update = _make_callback_update(callback_data="settings:close")
        context = MagicMock()

        await settings_callback(update, context)

        update.callback_query.answer.assert_awaited_once()
        update.callback_query.message.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_toggle_auto_fetch(self):
        update = _make_callback_update(
            user_id=42, callback_data="settings:toggle_auto_fetch"
        )
        context = MagicMock()

        with patch(
            "core.handlers.commands.toggle_auto_fetch_in_dm",
            new_callable=AsyncMock,
        ) as mock_toggle, patch(
            "core.handlers.commands.get_auto_fetch_in_dm",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "core.handlers.commands.get_force_refresh_cache",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await settings_callback(update, context)

        mock_toggle.assert_awaited_once_with(42)
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_toggle_force_refresh(self):
        update = _make_callback_update(
            user_id=42, callback_data="settings:toggle_force_refresh"
        )
        context = MagicMock()

        with patch(
            "core.handlers.commands.toggle_force_refresh_cache",
            new_callable=AsyncMock,
        ) as mock_toggle, patch(
            "core.handlers.commands.get_auto_fetch_in_dm",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "core.handlers.commands.get_force_refresh_cache",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await settings_callback(update, context)

        mock_toggle.assert_awaited_once_with(42)
        update.callback_query.edit_message_text.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args.kwargs["text"]
        assert "Force refresh cache: enabled" in text

    @pytest.mark.asyncio
    async def test_unknown_callback_data_returns_early(self):
        update = _make_callback_update(callback_data="settings:unknown")
        context = MagicMock()

        await settings_callback(update, context)

        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_not_awaited()
        update.callback_query.message.delete.assert_not_awaited()

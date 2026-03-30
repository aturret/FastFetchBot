from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from core.services.user_settings import (
    ensure_user_settings,
    get_auto_fetch_in_dm,
    toggle_auto_fetch_in_dm,
    get_force_refresh_cache,
    toggle_force_refresh_cache,
)


async def start_command(update: Update, context: CallbackContext) -> None:
    """Handle /start command: greet user and ensure settings row exists."""
    user_id = update.effective_user.id
    await ensure_user_settings(user_id)

    await update.message.reply_text(
        "Welcome to FastFetchBot!\n\n"
        "Send me a URL in this chat and I'll fetch the content for you.\n\n"
        "Available commands:\n"
        "/settings — Customize bot behavior\n"
    )


async def settings_command(update: Update, context: CallbackContext) -> None:
    """Handle /settings command: show current user settings with toggle buttons."""
    user_id = update.effective_user.id
    await ensure_user_settings(user_id)
    auto_fetch = await get_auto_fetch_in_dm(user_id)
    force_refresh = await get_force_refresh_cache(user_id)

    keyboard = _build_settings_keyboard(auto_fetch, force_refresh)
    await update.message.reply_text(
        text=_build_settings_text(auto_fetch, force_refresh),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def settings_callback(update: Update, context: CallbackContext) -> None:
    """Handle settings toggle button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if data == "settings:close":
        await query.message.delete()
        return

    if data == "settings:toggle_auto_fetch":
        await toggle_auto_fetch_in_dm(user_id)
    elif data == "settings:toggle_force_refresh":
        await toggle_force_refresh_cache(user_id)
    else:
        return

    auto_fetch = await get_auto_fetch_in_dm(user_id)
    force_refresh = await get_force_refresh_cache(user_id)

    keyboard = _build_settings_keyboard(auto_fetch, force_refresh)
    await query.edit_message_text(
        text=_build_settings_text(auto_fetch, force_refresh),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _build_settings_keyboard(
    auto_fetch: bool, force_refresh: bool
) -> list[list[InlineKeyboardButton]]:
    auto_fetch_status = "ON" if auto_fetch else "OFF"
    force_refresh_status = "ON" if force_refresh else "OFF"
    return [
        [
            InlineKeyboardButton(
                f"Auto-fetch in DM: {auto_fetch_status}",
                callback_data="settings:toggle_auto_fetch",
            )
        ],
        [
            InlineKeyboardButton(
                f"Force refresh cache: {force_refresh_status}",
                callback_data="settings:toggle_force_refresh",
            )
        ],
        [
            InlineKeyboardButton("Close", callback_data="settings:close"),
        ],
    ]


def _build_settings_text(auto_fetch: bool, force_refresh: bool) -> str:
    auto_fetch_status = "enabled" if auto_fetch else "disabled"
    force_refresh_status = "enabled" if force_refresh else "disabled"
    return (
        f"Your Settings\n\n"
        f"Auto-fetch in DM: {auto_fetch_status}\n"
        f"When enabled, URLs sent in private chat will be automatically processed.\n"
        f"When disabled, you will see action buttons to choose how to process each URL.\n\n"
        f"Force refresh cache: {force_refresh_status}\n"
        f"When enabled, cached results are ignored and content is always re-scraped."
    )

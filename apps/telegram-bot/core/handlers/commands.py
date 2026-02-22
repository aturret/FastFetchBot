from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from sqlalchemy import select

from fastfetchbot_shared.database.session import get_session
from fastfetchbot_shared.database.models.user_setting import UserSetting
from fastfetchbot_shared.utils.logger import logger
from core.services.user_settings import ensure_user_settings


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

    async with get_session() as session:
        result = await session.execute(
            select(UserSetting).where(UserSetting.telegram_user_id == user_id)
        )
        user_setting = result.scalar_one_or_none()

    auto_fetch = user_setting.auto_fetch_in_dm if user_setting else True

    keyboard = _build_settings_keyboard(auto_fetch)
    await update.message.reply_text(
        text=_build_settings_text(auto_fetch),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def settings_callback(update: Update, context: CallbackContext) -> None:
    """Handle settings toggle button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "settings:close":
        await query.message.delete()
        return

    if data != "settings:toggle_auto_fetch":
        return

    user_id = update.effective_user.id

    async with get_session() as session:
        result = await session.execute(
            select(UserSetting).where(UserSetting.telegram_user_id == user_id)
        )
        user_setting = result.scalar_one_or_none()

        if user_setting is None:
            # Safety fallback — should not happen since settings_command
            # already called ensure_user_settings, but handle gracefully.
            user_setting = UserSetting(
                telegram_user_id=user_id,
                auto_fetch_in_dm=False,
            )
            session.add(user_setting)
        else:
            user_setting.auto_fetch_in_dm = not user_setting.auto_fetch_in_dm

        new_value = user_setting.auto_fetch_in_dm

    keyboard = _build_settings_keyboard(new_value)
    await query.edit_message_text(
        text=_build_settings_text(new_value),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _build_settings_keyboard(auto_fetch: bool) -> list[list[InlineKeyboardButton]]:
    status = "ON" if auto_fetch else "OFF"
    return [
        [
            InlineKeyboardButton(
                f"Auto-fetch in DM: {status}",
                callback_data="settings:toggle_auto_fetch",
            )
        ],
        [
            InlineKeyboardButton("Close", callback_data="settings:close"),
        ],
    ]


def _build_settings_text(auto_fetch: bool) -> str:
    status = "enabled" if auto_fetch else "disabled"
    return (
        f"Your Settings\n\n"
        f"Auto-fetch in DM: {status}\n"
        f"When enabled, URLs sent in private chat will be automatically processed.\n"
        f"When disabled, you will see action buttons to choose how to process each URL."
    )

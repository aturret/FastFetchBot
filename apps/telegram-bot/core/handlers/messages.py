import html
import json
import traceback

from telegram import (
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackContext,
    ContextTypes,
)

from core.database import save_instances
from core.models.telegram_chat import TelegramMessage, TelegramUser, TelegramChat
from fastfetchbot_shared.utils.logger import logger
from core.config import (
    TELEBOT_DEBUG_CHANNEL,
    DATABASE_ON,
)


async def all_messages_process(update: Update, context: CallbackContext) -> None:
    message = update.message
    logger.debug(message)
    if message and DATABASE_ON:
        telegram_chat = TelegramChat.construct(**message.chat.to_dict())
        telegram_user = TelegramUser.construct(**message.from_user.to_dict())
        telegram_message = TelegramMessage(
            datetime=message.date,
            chat=telegram_chat,
            user=telegram_user,
            text=message.text or "",
        )
        await save_instances(telegram_message)


async def error_process(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    debug_chat_id = update.message.chat_id
    if TELEBOT_DEBUG_CHANNEL is not None:
        debug_chat_id = TELEBOT_DEBUG_CHANNEL
    await context.bot.send_message(
        chat_id=debug_chat_id, text=message, parse_mode=ParseMode.HTML
    )

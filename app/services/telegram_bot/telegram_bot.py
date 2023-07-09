# TODO: Implement Telegram Service
# example: https://docs.python-telegram-bot.org/en/stable/examples.customwebhookbot.html
import html
import json
import re
import traceback
import uuid
import logging

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    ContextTypes,
    TypeHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    InvalidCallbackData,
)

from app.config import (
    TELEGRAM_BOT_TOKEN,
    CHANNEL_ID,
)
from app.services.telegram_bot.telegram_bot_config import (
    HTTPS_URL_REGEX,
    WEBSITE_PATTERNS,
)

"""
application and handlers initialization
"""
application = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .updater(None)
    .arbitrary_callback_data(True)
    .build()
)
"""
logging
"""
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def set_webhook(url: str) -> None:
    await application.bot.set_webhook(url=url)


async def startup() -> None:
    await application.initialize()
    #  initialize handlers
    all_messages_handler = MessageHandler(
        filters=filters.ALL,
        callback=all_messages_process,
    )
    https_url_process_handler = MessageHandler(
        filters=filters.Regex(HTTPS_URL_REGEX),
        callback=https_url_process,
    )
    invalid_buttons_handler = CallbackQueryHandler(
        callback=invalid_buttons,
        pattern=InvalidCallbackData,
    )
    buttons_process_handler = CallbackQueryHandler(
        callback=buttons_process,
        # pattern=dict
    )
    #  add handlers
    application.add_handlers(
        [
            https_url_process_handler,
            all_messages_handler,
            invalid_buttons_handler,
            buttons_process_handler,
        ]
    )
    application.add_error_handler(error_handler)
    await application.start()


async def shutdown() -> None:
    await application.stop()


async def process_telegram_update(
        data: dict,
) -> None:
    """
    Process telegram update, put it to the update queue.
    :param data:
    :return:
    """
    await application.update_queue.put(Update.de_json(data=data, bot=application.bot))


async def https_url_process(update: Update, context: CallbackContext) -> None:
    url = context.matches[0].group(0)  # get first match by the context.matches
    message = update.message
    url_metadata = await check_url_type(url, message)
    if url_metadata["category"]:
        # process the metadata of the url
        await application.bot.delete_message(
            chat_id=message.chat_id,
            message_id=url_metadata.pop("replying_message").message_id,
        )
        url_metadata_id = str(uuid.uuid4())
        context.chat_data[url_metadata_id] = url_metadata
        # create the inline keyboard
        special_function_keyboard = []
        basic_function_keyboard = []
        if CHANNEL_ID:
            special_function_keyboard.append(
                InlineKeyboardButton(
                    "Send to channel",
                    callback_data={"type": "channel", "metadata": url_metadata},
                ),
            )
        basic_function_keyboard.append(
            InlineKeyboardButton(
                "Send to me",
                callback_data={"type": "private", "metadata": url_metadata},
            )
        )
        basic_function_keyboard.append(
            InlineKeyboardButton(
                "Cancel",
                callback_data={"type": "cancel"},
            )
        )
        keyboard = [
            special_function_keyboard,
            basic_function_keyboard,
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("Please choose:", reply_markup=reply_markup)


async def all_messages_process(update: Update, context: CallbackContext) -> None:
    print("webhook_update", update.message)
    return


async def buttons_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    id = query.id
    print(data, id)
    if data["type"] == "cancel":
        await query.answer("Canceled")
        await query.message.delete()
    elif data["type"] == "private":
        await query.answer("Sending to you...")
        await query.message.delete()
        # await content_process_function(query, context)
    elif data["type"] == "channel":
        await query.answer("Sending to channel...")
        await query.message.delete()
    context.drop_callback_data(query)


async def invalid_buttons(update: Update, context: CallbackContext) -> None:
    await update.callback_query.answer("Invalid button!")
    await update.effective_message.edit_text(
        "Sorry, I could not process this button click 😕 Please send /start to get a new keyboard."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    # tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    # tb_string = "".join(tb_list)
    # update_str = update.to_dict() if isinstance(update, Update) else str(update)
    # message = (
    #     f"An exception was raised while handling an update\n"
    #     f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
    #     "</pre>\n\n"
    #     f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
    #     f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
    #     f"<pre>{html.escape(tb_string)}</pre>"
    # )
    # await context.bot.send_message(
    #     chat_id=update.message.chat_id, text=message, parse_mode=ParseMode.HTML
    # )


async def check_url_type(url: str, message: telegram.Message) -> dict:
    for site, patterns in WEBSITE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url):
                replying_message = await message.reply_text(
                    text=f"{site} detected, please wait...",
                )
                url_metadata = {
                    "url": url,
                    "category": site,
                    "replying_message": replying_message,
                }
                return url_metadata
    replying_message = await message.reply_text(
        text="The url is not included in the list of supported websites.",
    )
    url_metadata = {
        "url": url,
        "category": None,
        "replying_message": replying_message,
    }
    return url_metadata

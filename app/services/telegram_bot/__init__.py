# TODO: Implement Telegram Service
# example: https://docs.python-telegram-bot.org/en/stable/examples.customwebhookbot.html
import html
import json
import logging
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    InvalidCallbackData,
)

from app.services.common import InfoExtractService
from app.utils.parse import check_url_type
from app.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
)
from .config import (
    HTTPS_URL_REGEX,
)

"""
logging
"""
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        callback=buttons_process, pattern=dict
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
    await application.bot.get_webhook_info()
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
    update = Update.de_json(data=data, bot=application.bot)
    application.bot.insert_callback_data(update)
    await application.update_queue.put(update)


async def https_url_process(update: Update, context: CallbackContext) -> None:
    message = update.message
    welcome_message = await message.reply_text(
        text="Processing...",
    )
    url = context.matches[0].group(0)  # get first match by the context.matches
    url_metadata = await check_url_type(url)
    if not url_metadata.source:
        await welcome_message.edit_text(text="No supported url found.")
        return
    else:
        await welcome_message.edit_text(
            text=f"{url_metadata.source} url found. Processing..."
        )
        # create the inline keyboard
        special_function_keyboard = []
        basic_function_keyboard = []
        if TELEGRAM_CHANNEL_ID:
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
        await welcome_message.delete()
        await message.reply_text("Please choose:", reply_markup=reply_markup)


async def all_messages_process(update: Update, context: CallbackContext) -> None:
    print("webhook_update", update.message)


async def buttons_process(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    if data["type"] == "cancel":
        await query.answer("Canceled")
    else:
        if data["type"] == "private":
            await query.answer("Sending to you...")
            chat_id = update.message.chat_id
            # await content_process_function(query, context)
            # TODO: sent to chat
        elif data["type"] == "channel":
            await query.answer("Sending to channel...")
            chat_id = TELEGRAM_CHANNEL_ID
            # TODO: sent to channel
        replying_message = await update.message.reply_text(
            text=f"Item processing...",
        )
        metadata_item = await content_process_function(data["metadata"])
        await replying_message.edit_text(
            text=f"Item processed. Sending to the target...",
        )
        await send_item_message(chat_id, metadata_item)
    await query.message.delete()
    context.drop_callback_data(query)


async def invalid_buttons(update: Update, context: CallbackContext) -> None:
    await update.callback_query.answer("Invalid button!")
    await update.effective_message.edit_text(
        "Sorry, I could not process this button click 😕 Please send /start to get a new keyboard."
    )


async def content_process_function(url_metadata: dict) -> dict:
    item = InfoExtractService(url_metadata)
    metadata_item = await item.get_item()
    return metadata_item


async def send_item_message(chat_id: int, item: dict):
    # TODO: send item message to channel or private
    pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await context.bot.send_message(
        chat_id=update.message.chat_id, text=message, parse_mode=ParseMode.HTML
    )


def message_formatting(data: dict) -> str:
    """
    Format the message to be sent to the user.
    :param data:
    :return:
    """
    text = (
        '<a href="'
        + data["telegraph_url"]
        + '"><b>'
        + data["title"]
        + "</b></a>\nvia #"
        + data["category"]
        + ' - <a href="'
        + data["author_url"]
        + ' "> '
        + data["author"]
        + "</a>\n"
        + data["message"]
        + '<a href="'
        + data["url"]
        + '">阅读原文</a>'
    )
    return text

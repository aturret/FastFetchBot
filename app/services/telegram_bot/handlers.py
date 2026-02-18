import html
import json
import traceback

from telegram import (
    Update,
    MessageEntity,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackContext,
    ContextTypes,
)

from app.database import save_instances
from app.models.metadata_item import MessageType
from app.models.telegram_chat import TelegramMessage, TelegramUser, TelegramChat
from app.models.url_metadata import UrlMetadata
from app.services.scrapers.common import InfoExtractService
from app.services.telegram_bot.message_sender import send_item_message
from app.utils.parse import get_url_metadata
from app.utils.config import SOCIAL_MEDIA_WEBSITE_PATTERNS, VIDEO_WEBSITE_PATTERNS
from app.utils.logger import logger
from app.config import (
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_CHANNEL_ADMIN_LIST,
    TELEBOT_DEBUG_CHANNEL,
    TELEGRAM_GROUP_MESSAGE_BAN_LIST,
    TELEGRAM_BOT_MESSAGE_BAN_LIST,
    FILE_EXPORTER_ON,
    OPENAI_API_KEY,
    DATABASE_ON,
    GENERAL_SCRAPING_ON,
)


async def content_process_function(url_metadata: UrlMetadata, **kwargs) -> dict:
    item = InfoExtractService(url_metadata, **kwargs)
    metadata_item = await item.get_item()
    return metadata_item


async def https_url_process(update: Update, context: CallbackContext) -> None:
    message = update.message
    welcome_message = await message.reply_text(
        text="Processing...",
    )
    url_dict: dict = message.parse_entities(types=["url"])
    await welcome_message.delete()
    for i, url in enumerate(url_dict.values()):
        process_message = await message.reply_text(
            text=f"Processing the {i + 1}th url...",
        )
        url_metadata = await get_url_metadata(url, ban_list=TELEGRAM_BOT_MESSAGE_BAN_LIST)
        if url_metadata.source == "banned":
            await process_message.edit_text(
                text=f"For the {i + 1} th url, the url is banned."
            )
            return
        if url_metadata.source == "unknown":
            if GENERAL_SCRAPING_ON:
                await process_message.edit_text(
                    text=f"Uncategorized url found. General webpage parser is on, Processing..."
                )
                metadata_item = await content_process_function(url_metadata=url_metadata)
                await send_item_message(
                    metadata_item, chat_id=message.chat_id
                )
            await process_message.edit_text(
                text=f"For the {i + 1} th url, no supported url found."
            )
            return
        else:
            await process_message.edit_text(
                text=f"{url_metadata.source} url found. Processing..."
            )
            # create the inline keyboard
            special_function_keyboard = []
            basic_function_keyboard = []
            if TELEGRAM_CHANNEL_ID and (
                    TELEGRAM_CHANNEL_ADMIN_LIST
                    and str(message.from_user.id) in TELEGRAM_CHANNEL_ADMIN_LIST
            ):
                special_function_keyboard.append(
                    InlineKeyboardButton(
                        "Send to Channel",
                        callback_data={
                            "type": "channel",
                            "metadata": url_metadata,
                            "extra_args": {"store_document": True},
                        },
                    ),
                )
            # video content url buttons
            if url_metadata.content_type == "video":
                basic_function_keyboard.extend(
                    [
                        InlineKeyboardButton(
                            "Get Info",
                            callback_data={
                                "type": "video",
                                "metadata": url_metadata,
                                "extra_args": {"download": False},
                            },
                        ),
                        InlineKeyboardButton(
                            "Download",
                            callback_data={
                                "type": "video",
                                "metadata": url_metadata,
                            },
                        ),
                    ]
                )
                if FILE_EXPORTER_ON:
                    special_function_keyboard.extend(
                        [
                            InlineKeyboardButton(
                                "Audio Only",
                                callback_data={
                                    "type": "video",
                                    "metadata": url_metadata,
                                    "extra_args": {
                                        "audio_only": True,
                                    },
                                },
                            ),
                            InlineKeyboardButton(
                                "Download HD",
                                callback_data={
                                    "type": "video",
                                    "metadata": url_metadata,
                                    "extra_args": {"hd": True},
                                },
                            ),
                        ]
                    )
                    if OPENAI_API_KEY:
                        special_function_keyboard.append(
                            InlineKeyboardButton(
                                "Transcribe Text",
                                callback_data={
                                    "type": "video",
                                    "metadata": url_metadata,
                                    "extra_args": {
                                        "audio_only": True,
                                        "transcribe": True,
                                        "store_document": True,
                                    },
                                },
                            ),
                        )
            elif url_metadata.content_type == "social_media":
                basic_function_keyboard.extend(
                    [
                        InlineKeyboardButton(
                            "Send to Me",
                            callback_data={"type": "private", "metadata": url_metadata},
                        ),
                        InlineKeyboardButton(
                            "Force Send in Chat",
                            callback_data={"type": "force", "metadata": url_metadata},
                        ),
                    ]
                )
                if FILE_EXPORTER_ON:
                    special_function_keyboard.append(
                        InlineKeyboardButton(
                            "Send with PDF",
                            callback_data={
                                "type": "pdf",
                                "metadata": url_metadata,
                                "extra_args": {"store_document": True},
                            },
                        ),
                    )
            basic_function_keyboard.append(
                InlineKeyboardButton(
                    "Cancel",
                    callback_data={"type": "cancel"},
                ),
            )
            keyboard = [
                special_function_keyboard,
                basic_function_keyboard,
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await process_message.reply_text(
                f"For the {i + 1}th url: {url}, please choose the function you want to use:",
                reply_markup=reply_markup,
            )
            await process_message.delete()


async def https_url_auto_process(update: Update, context: CallbackContext) -> None:
    message = update.message
    url_dict = message.parse_entities(types=["url"])
    for i, url in enumerate(url_dict.values()):
        url_metadata = await get_url_metadata(
            url, ban_list=TELEGRAM_GROUP_MESSAGE_BAN_LIST
        )
        if url_metadata.source == "unknown" and GENERAL_SCRAPING_ON:
            metadata_item = await content_process_function(url_metadata=url_metadata)
            await send_item_message(
                metadata_item, chat_id=message.chat_id, message=message
            )
        elif url_metadata.source == "unknown" or url_metadata.source == "banned":
            logger.debug(f"for the {i + 1}th url {url}, no supported url found.")
            return
        if url_metadata.to_dict().get("source") in SOCIAL_MEDIA_WEBSITE_PATTERNS.keys():
            metadata_item = await content_process_function(url_metadata=url_metadata)
            await send_item_message(
                metadata_item, chat_id=message.chat_id, message=message
            )
        if url_metadata.to_dict().get("source") in VIDEO_WEBSITE_PATTERNS.keys():
            metadata_item = await content_process_function(url_metadata=url_metadata)
            await send_item_message(
                metadata_item, chat_id=message.chat_id, message=message
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


async def buttons_process(update: Update, context: CallbackContext) -> None:
    from app.services.telegram_bot import application

    query = update.callback_query
    data = query.data
    chat_id = None
    if data["type"] == "cancel":
        await query.answer("Canceled")
    else:
        if data["type"] == "private" or data["type"] == "force":
            await query.answer("Sending to you...")
        if data["type"] == "channel":
            if data.get("channel_id") or len(TELEGRAM_CHANNEL_ID) == 1:
                channel_chat = await application.bot.get_chat(
                    chat_id=data.get("channel_id")
                    if data.get("channel_id")
                    else TELEGRAM_CHANNEL_ID[0]
                )
                await query.answer("Sending to channel...")
                if channel_chat.type == "channel":
                    chat_id = channel_chat.id
                else:
                    await query.message.reply_text(
                        text="Sorry, the provided channel id does not exist or is not a channel."
                    )
                    chat_id = query.message.chat_id
            elif len(TELEGRAM_CHANNEL_ID) > 1:
                choose_channel_keyboard = await _create_choose_channel_keyboard(
                    data=data
                )
                await query.message.reply_text(
                    text="Please choose the channel you want to send:",
                    reply_markup=InlineKeyboardMarkup(choose_channel_keyboard),
                )
                await query.message.delete()
                context.drop_callback_data(query)
                return
        else:
            chat_id = query.message.chat_id
        if data["type"] == "video":
            await query.answer("Video processing...")
        replying_message = await query.message.reply_text(
            text=f"Item processing...",
        )
        extra_args = data["extra_args"] if "extra_args" in data else {}
        metadata_item = await content_process_function(
            url_metadata=data["metadata"], **extra_args
        )
        await replying_message.edit_text(
            text=f"Item processed. Sending to the target...",
        )
        if data["type"] == "force":
            metadata_item["message_type"] = MessageType.SHORT
        await send_item_message(metadata_item, chat_id=chat_id)
        if data["type"] == "channel":
            await query.message.reply_text(
                text=f"Item sent to the channel.",
            )
        await replying_message.delete()
    await query.message.delete()
    context.drop_callback_data(query)


async def _create_choose_channel_keyboard(data: dict) -> list:
    from app.services.telegram_bot import application

    choose_channel_keyboard = []
    for i, channel_id in enumerate(TELEGRAM_CHANNEL_ID):
        channel_chat = await application.bot.get_chat(chat_id=channel_id)
        choose_channel_keyboard.append(
            [
                InlineKeyboardButton(
                    channel_chat.title,
                    callback_data={
                        "type": "channel",
                        "metadata": data["metadata"],
                        "extra_args": data["extra_args"],
                        "channel_id": channel_id,
                    },
                )
            ]
        )
    choose_channel_keyboard.append(
        [
            InlineKeyboardButton(
                "Cancel",
                callback_data={"type": "cancel"},
            )
        ]
    )
    return choose_channel_keyboard


async def invalid_buttons(update: Update, context: CallbackContext) -> None:
    await update.callback_query.answer("Invalid button!")
    await update.effective_message.edit_text(
        "Sorry, Error Occurred, I could not process this button click 😕."
    )


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

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
)

from core import api_client
from core.services.message_sender import send_item_message
from fastfetchbot_shared.utils.config import SOCIAL_MEDIA_WEBSITE_PATTERNS, VIDEO_WEBSITE_PATTERNS
from fastfetchbot_shared.utils.logger import logger
from core.config import (
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_CHANNEL_ADMIN_LIST,
    TELEGRAM_GROUP_MESSAGE_BAN_LIST,
    TELEGRAM_BOT_MESSAGE_BAN_LIST,
    FILE_EXPORTER_ON,
    OPENAI_API_KEY,
    GENERAL_SCRAPING_ON,
)


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
        url_metadata = await api_client.get_url_metadata(url, ban_list=TELEGRAM_BOT_MESSAGE_BAN_LIST)
        if url_metadata["source"] == "banned":
            await process_message.edit_text(
                text=f"For the {i + 1} th url, the url is banned."
            )
            return
        if url_metadata["source"] == "unknown":
            if GENERAL_SCRAPING_ON:
                await process_message.edit_text(
                    text=f"Uncategorized url found. General webpage parser is on, Processing..."
                )
                metadata_item = await api_client.get_item(url=url_metadata["url"])
                await send_item_message(
                    metadata_item, chat_id=message.chat_id
                )
            await process_message.edit_text(
                text=f"For the {i + 1} th url, no supported url found."
            )
            return
        else:
            await process_message.edit_text(
                text=f"{url_metadata['source']} url found. Processing..."
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
                            "url": url_metadata["url"],
                            "source": url_metadata["source"],
                            "content_type": url_metadata["content_type"],
                            "extra_args": {"store_document": True},
                        },
                    ),
                )
            # video content url buttons
            if url_metadata["content_type"] == "video":
                basic_function_keyboard.extend(
                    [
                        InlineKeyboardButton(
                            "Get Info",
                            callback_data={
                                "type": "video",
                                "url": url_metadata["url"],
                                "source": url_metadata["source"],
                                "content_type": url_metadata["content_type"],
                                "extra_args": {"download": False},
                            },
                        ),
                        InlineKeyboardButton(
                            "Download",
                            callback_data={
                                "type": "video",
                                "url": url_metadata["url"],
                                "source": url_metadata["source"],
                                "content_type": url_metadata["content_type"],
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
                                    "url": url_metadata["url"],
                                    "source": url_metadata["source"],
                                    "content_type": url_metadata["content_type"],
                                    "extra_args": {
                                        "audio_only": True,
                                    },
                                },
                            ),
                            InlineKeyboardButton(
                                "Download HD",
                                callback_data={
                                    "type": "video",
                                    "url": url_metadata["url"],
                                    "source": url_metadata["source"],
                                    "content_type": url_metadata["content_type"],
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
                                    "url": url_metadata["url"],
                                    "source": url_metadata["source"],
                                    "content_type": url_metadata["content_type"],
                                    "extra_args": {
                                        "audio_only": True,
                                        "transcribe": True,
                                        "store_document": True,
                                    },
                                },
                            ),
                        )
            elif url_metadata["content_type"] == "social_media":
                basic_function_keyboard.extend(
                    [
                        InlineKeyboardButton(
                            "Send to Me",
                            callback_data={
                                "type": "private",
                                "url": url_metadata["url"],
                                "source": url_metadata["source"],
                                "content_type": url_metadata["content_type"],
                            },
                        ),
                        InlineKeyboardButton(
                            "Force Send in Chat",
                            callback_data={
                                "type": "force",
                                "url": url_metadata["url"],
                                "source": url_metadata["source"],
                                "content_type": url_metadata["content_type"],
                            },
                        ),
                    ]
                )
                if FILE_EXPORTER_ON:
                    special_function_keyboard.append(
                        InlineKeyboardButton(
                            "Send with PDF",
                            callback_data={
                                "type": "pdf",
                                "url": url_metadata["url"],
                                "source": url_metadata["source"],
                                "content_type": url_metadata["content_type"],
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
        url_metadata = await api_client.get_url_metadata(
            url, ban_list=TELEGRAM_GROUP_MESSAGE_BAN_LIST
        )
        if url_metadata["source"] == "unknown" and GENERAL_SCRAPING_ON:
            metadata_item = await api_client.get_item(url=url_metadata["url"])
            await send_item_message(
                metadata_item, chat_id=message.chat_id, message=message
            )
        elif url_metadata["source"] == "unknown" or url_metadata["source"] == "banned":
            logger.debug(f"for the {i + 1}th url {url}, no supported url found.")
            return
        if url_metadata.get("source") in SOCIAL_MEDIA_WEBSITE_PATTERNS.keys():
            metadata_item = await api_client.get_item(url=url_metadata["url"])
            await send_item_message(
                metadata_item, chat_id=message.chat_id, message=message
            )
        if url_metadata.get("source") in VIDEO_WEBSITE_PATTERNS.keys():
            metadata_item = await api_client.get_item(url=url_metadata["url"])
            await send_item_message(
                metadata_item, chat_id=message.chat_id, message=message
            )

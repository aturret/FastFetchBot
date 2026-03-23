from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
)

from core.services.message_sender import send_item_message
from core.services.user_settings import get_auto_fetch_in_dm
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
    SCRAPE_MODE,
)


async def _get_url_metadata(url: str, ban_list: list | None = None) -> dict:
    """Resolve URL metadata via API or shared library depending on SCRAPE_MODE.

    In API mode: calls the API server's /scraper/getUrlMetadata endpoint.
    In queue mode: calls the shared library's get_url_metadata directly
    (pure URL parsing, no network call needed).
    """
    if SCRAPE_MODE == "queue":
        from fastfetchbot_shared.utils.parse import get_url_metadata as shared_get_url_metadata

        url_metadata = await shared_get_url_metadata(url, ban_list=ban_list)
        return url_metadata.to_dict()
    else:
        from core import api_client

        return await api_client.get_url_metadata(url, ban_list=ban_list)


async def _fetch_and_send(
    url: str,
    chat_id: int | str,
    message_id: int | None = None,
    source: str = "",
    content_type: str = "",
    message=None,
    **kwargs,
) -> None:
    """Fetch an item via API or queue depending on SCRAPE_MODE.

    Args:
        url: The resolved URL to scrape.
        chat_id: Target chat for the result.
        message_id: Optional message ID for reply threading.
        source: Pre-resolved source platform (e.g. "twitter").
        content_type: Pre-resolved content type (e.g. "social_media").
        message: Optional telegram Message for reply context.
        **kwargs: Extra arguments passed to the scraper.
    """
    if SCRAPE_MODE == "queue":
        from core import queue_client

        await queue_client.enqueue_scrape(
            url=url,
            chat_id=chat_id,
            message_id=message_id if message_id is not None else (message.message_id if message else None),
            source=source,
            content_type=content_type,
            **kwargs,
        )
    else:
        from core import api_client

        metadata_item = await api_client.get_item(url=url, **kwargs)
        await send_item_message(metadata_item, chat_id=chat_id, message=message)


async def https_url_process(update: Update, context: CallbackContext) -> None:
    message = update.message

    # Check user's auto-fetch preference
    auto_fetch = await get_auto_fetch_in_dm(message.from_user.id)
    if auto_fetch:
        await _auto_fetch_urls(message)
        return

    welcome_message = await message.reply_text(
        text="Processing...",
    )
    url_dict: dict = message.parse_entities(types=["url"])
    await welcome_message.delete()
    for i, url in enumerate(url_dict.values()):
        process_message = await message.reply_text(
            text=f"Processing the {i + 1}th url...",
        )
        url_metadata = await _get_url_metadata(url, ban_list=TELEGRAM_BOT_MESSAGE_BAN_LIST)
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
                await _fetch_and_send(
                    url=url_metadata["url"],
                    chat_id=message.chat_id,
                    source=url_metadata.get("source", ""),
                    content_type=url_metadata.get("content_type", ""),
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


async def _auto_fetch_urls(message) -> None:
    """Auto-fetch all URLs in a DM message without showing action buttons."""
    url_dict = message.parse_entities(types=["url"])
    for i, url in enumerate(url_dict.values()):
        url_metadata = await _get_url_metadata(
            url, ban_list=TELEGRAM_BOT_MESSAGE_BAN_LIST
        )
        if url_metadata["source"] == "unknown" and GENERAL_SCRAPING_ON:
            await _fetch_and_send(
                url=url_metadata["url"],
                chat_id=message.chat_id,
                source=url_metadata.get("source", ""),
                content_type=url_metadata.get("content_type", ""),
            )
        elif url_metadata["source"] == "unknown" or url_metadata["source"] == "banned":
            logger.debug(f"for the {i + 1}th url {url}, no supported url found.")
            continue
        if url_metadata.get("source") in SOCIAL_MEDIA_WEBSITE_PATTERNS.keys():
            await _fetch_and_send(
                url=url_metadata["url"],
                chat_id=message.chat_id,
                source=url_metadata.get("source", ""),
                content_type=url_metadata.get("content_type", ""),
            )
        if url_metadata.get("source") in VIDEO_WEBSITE_PATTERNS.keys():
            await _fetch_and_send(
                url=url_metadata["url"],
                chat_id=message.chat_id,
                source=url_metadata.get("source", ""),
                content_type=url_metadata.get("content_type", ""),
            )


async def https_url_auto_process(update: Update, context: CallbackContext) -> None:
    message = update.message
    url_dict = message.parse_entities(types=["url"])
    for i, url in enumerate(url_dict.values()):
        url_metadata = await _get_url_metadata(
            url, ban_list=TELEGRAM_GROUP_MESSAGE_BAN_LIST
        )
        if url_metadata["source"] == "unknown" and GENERAL_SCRAPING_ON:
            await _fetch_and_send(
                url=url_metadata["url"],
                chat_id=message.chat_id,
                message=message,
                source=url_metadata.get("source", ""),
                content_type=url_metadata.get("content_type", ""),
            )
        elif url_metadata["source"] == "unknown" or url_metadata["source"] == "banned":
            logger.debug(f"for the {i + 1}th url {url}, no supported url found.")
            return
        if url_metadata.get("source") in SOCIAL_MEDIA_WEBSITE_PATTERNS.keys():
            await _fetch_and_send(
                url=url_metadata["url"],
                chat_id=message.chat_id,
                message=message,
                source=url_metadata.get("source", ""),
                content_type=url_metadata.get("content_type", ""),
            )
        if url_metadata.get("source") in VIDEO_WEBSITE_PATTERNS.keys():
            await _fetch_and_send(
                url=url_metadata["url"],
                chat_id=message.chat_id,
                message=message,
                source=url_metadata.get("source", ""),
                content_type=url_metadata.get("content_type", ""),
            )

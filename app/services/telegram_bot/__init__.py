# TODO: Implement Telegram Service
# example: https://docs.python-telegram-bot.org/en/stable/examples.customwebhookbot.html
import asyncio
import html
import json
import logging
import os
import traceback
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import url2pathname
from typing import Optional, Union

import aiofiles
from telegram import (
    Update,
    MessageEntity,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InputFile,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAnimation,
    InputMediaAudio,
)
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
from jinja2 import Environment, FileSystemLoader

from app.services.common import InfoExtractService
from app.utils.parse import check_url_type
from app.utils.network import download_a_iobytes_file
from app.utils.image import Image, image_compressing
from app.utils.config import SOCIAL_MEDIA_WEBSITE_PATTERNS
from app.utils.logger import logger
from app.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    TELEBOT_API_SERVER,
    TELEBOT_API_SERVER_FILE,
    TELEBOT_LOCAL_FILE_MODE,
    TELEBOT_CONNECT_TIMEOUT,
    TELEBOT_READ_TIMEOUT,
    TELEBOT_WRITE_TIMEOUT,
    TELEGRAM_IMAGE_DIMENSION_LIMIT,
    TELEGRAM_IMAGE_SIZE_LIMIT,
    JINJA2_ENV,
)
from app.services.telegram_bot.config import (
    HTTPS_URL_REGEX,
    TELEGRAM_SINGLE_MESSAGE_MEDIA_LIMIT,
    TELEGRAM_FILE_UPLOAD_LIMIT,
    TELEGRAM_FILE_UPLOAD_LIMIT_LOCAL_API,
    REFERER_REQUIRED,
)
from app.models.classes import NamedBytesIO
from app.models.url_metadata import UrlMetadata

"""
application and handlers initialization
"""
logger.debug(
    f"""
TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN}
TELEGRAM_CHANNEL_ID: {TELEGRAM_CHANNEL_ID}
TELEBOT_API_SERVER: {TELEBOT_API_SERVER}
TELEBOT_API_SERVER_FILE: {TELEBOT_API_SERVER_FILE}
LOCAL_FILE_MODE: {TELEBOT_LOCAL_FILE_MODE}
"""
)
if TELEGRAM_BOT_TOKEN is not None:
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .updater(None)
        .arbitrary_callback_data(True)
        .connect_timeout(TELEBOT_CONNECT_TIMEOUT)
        .read_timeout(TELEBOT_READ_TIMEOUT)
        .write_timeout(TELEBOT_WRITE_TIMEOUT)
        .base_url(TELEBOT_API_SERVER)
        .base_file_url(TELEBOT_API_SERVER_FILE)
        .local_mode(TELEBOT_LOCAL_FILE_MODE)
        .build()
    )
else:
    logger.error("TELEGRAM_BOT_TOKEN is not set!")

environment = JINJA2_ENV
template = environment.get_template("social_media_message.jinja2")


async def set_webhook(url: str) -> None:
    await application.bot.set_webhook(url=url)


async def startup() -> None:
    await application.initialize()
    # initialize handlers
    all_messages_handler = MessageHandler(
        filters=filters.ALL,
        callback=all_messages_process,
    )
    https_url_process_handler = MessageHandler(
        filters=filters.ChatType.PRIVATE
        & filters.Entity(MessageEntity.URL)
        & (~filters.FORWARDED)
        & filters.USER,
        callback=https_url_process,
    )
    https_url_auto_process_handler = MessageHandler(
        filters=(
            filters.ChatType.SUPERGROUP
            | filters.ChatType.GROUP
            | filters.ChatType.GROUPS
        )
        & filters.Entity(MessageEntity.URL)
        & (~filters.FORWARDED)
        & filters.USER,
        callback=https_url_auto_process,
    )
    invalid_buttons_handler = CallbackQueryHandler(
        callback=invalid_buttons,
        pattern=InvalidCallbackData,
    )
    buttons_process_handler = CallbackQueryHandler(
        callback=buttons_process, pattern=dict
    )
    # add handlers
    application.add_handlers(
        [
            https_url_process_handler,
            https_url_auto_process_handler,
            all_messages_handler,
            invalid_buttons_handler,
            buttons_process_handler,
        ]
    )
    application.add_error_handler(error_handler)
    webhook_info = await application.bot.get_webhook_info()
    logger.debug("webhook info: " + str(webhook_info))
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
    logger.debug(f"update: {update}")
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
                    "Send to Channel",
                    callback_data={"type": "channel", "metadata": url_metadata},
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
            special_function_keyboard.extend(
                [
                    InlineKeyboardButton(
                        "Transcribe Text",
                        callback_data={
                            "type": "video",
                            "metadata": url_metadata,
                            "extra_args": {"audio_only": True},
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
        elif url_metadata.content_type == "social_media":
            special_function_keyboard.append(
                InlineKeyboardButton(
                    "Force Send in Chat",
                    callback_data={"type": "force", "metadata": url_metadata},
                )
            )
            basic_function_keyboard.append(
                InlineKeyboardButton(
                    "Send to Me",
                    callback_data={"type": "private", "metadata": url_metadata},
                )
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
        await welcome_message.delete()
        await message.reply_text("Please choose:", reply_markup=reply_markup)


async def https_url_auto_process(update: Update, context: CallbackContext) -> None:
    message = update.message
    url = context.matches[0].group(0)
    url_metadata = await check_url_type(url)
    if not url_metadata.source:
        logger.debug(f"for url {url}, no supported url found.")
        return
    if url_metadata.to_dict().get("source") in SOCIAL_MEDIA_WEBSITE_PATTERNS.keys():
        metadata_item = await content_process_function(url_metadata=url_metadata)
        await send_item_message(metadata_item, chat_id=message.chat_id, message=message)


async def all_messages_process(update: Update, context: CallbackContext) -> None:
    print("webhook_update", update.message)


async def buttons_process(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    chat_id = None
    if data["type"] == "cancel":
        await query.answer("Canceled")
    else:
        if data["type"] == "private":
            await query.answer("Sending to you...")
        if data["type"] == "channel":
            await query.answer("Sending to channel...")
            chat_id = await application.bot.get_chat(chat_id=TELEGRAM_CHANNEL_ID).id
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
        await send_item_message(metadata_item, chat_id=chat_id, message=query.message)
    await query.message.delete()
    context.drop_callback_data(query)


async def invalid_buttons(update: Update, context: CallbackContext) -> None:
    await update.callback_query.answer("Invalid button!")
    await update.effective_message.edit_text(
        "Sorry, I could not process this button click 😕 Please send /start to get a new keyboard."
    )


async def content_process_function(url_metadata: UrlMetadata, **kwargs) -> dict:
    item = InfoExtractService(url_metadata, **kwargs)
    metadata_item = await item.get_item()
    return metadata_item


async def send_item_message(
    data: dict, chat_id: Union[int, str] = None, message: Message = None
) -> None:
    """
    :param data: (dict) metadata of the item
    :param chat_id: (int) any chat id for sending
    :param message: (Message) any message to reply
    :return:
    """
    if not chat_id and not message:
        raise ValueError("must provide chat_id or message")
    if (
        not chat_id
    ) and message:  # this function supports directly reply to a message even if the chat_id is None
        chat_id = message.chat.id
    discussion_chat_id = chat_id
    the_chat = await application.bot.get_chat(chat_id=chat_id)
    if the_chat.type == "channel":
        if the_chat.linked_chat_id:
            discussion_chat_id = the_chat.linked_chat_id
    try:
        caption_text = message_formatting(data)
        if data["message_type"] == "short" and len(data["media_files"]) > 0:
            # if the message type is short and there are some media files, send media group
            media_message_group, file_group = await media_files_packaging(
                media_files=data["media_files"], data=data
            )
            if (
                len(media_message_group) > 0
            ):  # if there are some media groups to send, send it
                reply_to_message_id = None
                for i, media_group in enumerate(media_message_group):
                    caption_text = (
                        caption_text
                        if i == 0
                        else f"the {i + 1}th part of the media item:"
                    )
                    logger.debug(f"media group: {media_group}")
                    sent_message = await application.bot.send_media_group(
                        chat_id=discussion_chat_id,
                        media=media_group,
                        parse_mode=ParseMode.HTML,
                        caption=caption_text,
                    )
                if discussion_chat_id != chat_id > 0:
                    # if the chat is a channel, get the latest pinned message from the channel and reply to it
                    pinned_message = await application.bot.get_chat(
                        chat_id=discussion_chat_id
                    ).pinned_message
                    if (
                        pinned_message.forward_from_message_id
                        == sent_message[-1].message_id
                    ):
                        reply_to_message_id = (
                            application.bot.get_chat(
                                chat_id=discussion_chat_id
                            ).pinned_message.id
                            - len(sent_message)
                            + 1
                        )
                    else:
                        reply_to_message_id = sent_message[-1].message_id
            if (
                len(file_group) > 0
            ):  # send files, the files messages should be replied to the message sent before
                application.bot.send_message(
                    chat_id=discussion_chat_id,
                    parse_mode=ParseMode.HTML,
                    text="The following files are larger than the limitation of Telegram, "
                    "so they are sent as files:",
                    reply_to_message_id=reply_to_message_id,
                )
                for file in file_group:
                    if file.name.endswith(
                        ".gif"
                    ):  # TODO: it's not a good way to determine whether it's a gif.
                        await application.bot.send_video(
                            chat_id=discussion_chat_id,
                            animation=file,
                            reply_to_message_id=reply_to_message_id,
                            parse_mode=ParseMode.HTML,
                        )
                    else:
                        await application.bot.send_document(
                            chat_id=discussion_chat_id,
                            document=file,
                            reply_to_message_id=reply_to_message_id,
                            parse_mode=ParseMode.HTML,
                        )
        else:  # if there are no media files, send the caption text and also note the message
            await application.bot.send_message(
                chat_id=discussion_chat_id,
                text=caption_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        await message.reply_text(
            text="Sorry, I could not send the item to the target 😕"
        )


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
    :return: text (str) the formatted text for telegram bot api sending message.
    """
    message_template = template
    text = message_template.render(data=data)
    print(text)
    return text


async def media_files_packaging(media_files: list, data: dict) -> tuple:
    """
    Download the media files from data["media_files"] and package them into a list of media group or file group for
    sending them by send_media_group method or send_document method.
    :param data: (dict) metadata of the item
    :param media_files: (list) a list of media files,
    :param caption_text: (str) the caption text
    :return: (tuple) a tuple of media group and file group
        media_message_group: (list) a list of media items, the type of each item is InputMediaPhoto or InputMediaVideo
        file_group: (list) a list of file items, the type of each item is InputFile
    TODO: It's not a good practice for this function. This method will still download all the media files even when
        media files are too large and it can be memory consuming even if we use a database to store the media files.
        The function should be optimized to resolve the media files one group by one group and send each group
        immediately after it is resolved.
        This processing method should be optimized in the future.
    """
    media_counter = 0
    media_message_group = []
    media_group = []
    file_group = []
    for (
        media_item
    ) in media_files:  # To traverse all media items in the media files list
        # check if we need to create a new media group
        if media_counter == TELEGRAM_SINGLE_MESSAGE_MEDIA_LIMIT:
            # the limitation of media item for a single telegram media group message is 10
            media_message_group.append(media_group)
            media_group = []
            media_counter = 0
        # check the url validity
        url_parser = urlparse(media_item["url"])
        if url_parser.scheme in [
            "http",
            "https",
        ]:  # if the url is a http url, download the file
            referer = data["url"] if data["category"] in REFERER_REQUIRED else None
            file_format = "mp4" if media_item["media_type"] == "video" else None
            io_object = await download_a_iobytes_file(
                media_item["url"], file_format=file_format, referer=referer
            )
            filename = io_object.name
            file_size = io_object.size
        else:  # if the url is a local file path, just add it to the media group
            try:
                file_path = url2pathname(media_item["url"])
                async with aiofiles.open(file_path, mode="rb") as f:
                    filename = os.path.basename(file_path)
                    content = await f.read()
                    io_object = NamedBytesIO(content=content, name=filename)
                file_size = io_object.size
            except Exception as e:  # the url is not a valid file path
                logger.error(e)
                continue
        # check the file size
        if (
            not TELEBOT_API_SERVER
        ):  # the official telegram bot api server only supports 50MB file
            if file_size > TELEGRAM_FILE_UPLOAD_LIMIT:
                # if the size is over 50MB, skip this file
                continue
        else:
            if file_size > TELEGRAM_FILE_UPLOAD_LIMIT_LOCAL_API:
                # for local api sever, if the size is over 2GB, skip this file
                continue
        # check media files' type and process them by their type
        if media_item["media_type"] == "image":
            image_url = media_item["url"]
            image = Image.open(io_object)
            img_width, img_height = image.size
            image = image_compressing(image, 2 * TELEGRAM_IMAGE_DIMENSION_LIMIT)
            with BytesIO() as buffer:
                image.save(buffer, format=image.format)
                buffer.seek(0)
                media_group.append(InputMediaPhoto(buffer, filename=filename))
            # the image is not able to get json serialized
            if (
                file_size > TELEGRAM_IMAGE_SIZE_LIMIT
                or img_width > TELEGRAM_IMAGE_DIMENSION_LIMIT
                or img_height > TELEGRAM_IMAGE_DIMENSION_LIMIT
            ):
                io_object = await download_a_iobytes_file(url=image_url)
                if not io_object.name.endswith(".gif"):
                    # TODO: it is not a good way to judge whether it is a gif...
                    file_group.append(io_object)
        elif media_item["media_type"] == "gif":
            io_object = await download_a_iobytes_file(
                url=media_item["url"],
                file_name="gif_image-" + str(media_counter) + ".gif",
            )
            io_object.name = io_object.name + ".gif"
            media_group.append(InputMediaAnimation(io_object))
        elif media_item["media_type"] == "video":
            media_group.append(InputMediaVideo(io_object, supports_streaming=True))
        # TODO: not have any services to store audio files for now, just a placeholder
        elif media_item["media_type"] == "audio":
            media_group.append(InputMediaAudio(io_object))
        media_counter += 1
        logger.info(
            f"get the {media_counter}th media item,type: {media_item['media_type']}, url: {media_item['url']}"
        )
    # check if the media group is empty, if it is, return None
    if len(media_message_group) == 0:
        if len(media_group) == 0:
            return media_message_group, file_group
        else:  # if the media group is not empty, append the only media group
            media_message_group.append(media_group)
    elif len(media_group) > 0:  # append the last media group
        media_message_group.append(media_group)
    return media_message_group, file_group

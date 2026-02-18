import asyncio
import os
import traceback
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import url2pathname
from typing import Union

import aiofiles
from telegram import (
    Message,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAnimation,
    InputMediaAudio,
)
from telegram.constants import ParseMode

from app.models.metadata_item import MessageType
from app.models.classes import NamedBytesIO
from app.utils.parse import telegram_message_html_trim
from app.utils.network import download_file_by_metadata_item
from app.utils.image import Image, image_compressing, check_image_type
from app.utils.logger import logger
from app.config import (
    TELEBOT_API_SERVER,
    TELEBOT_WRITE_TIMEOUT,
    TELEGRAM_IMAGE_DIMENSION_LIMIT,
    TELEGRAM_IMAGE_SIZE_LIMIT,
    JINJA2_ENV,
    TEMPLATE_LANGUAGE,
)
from app.services.telegram_bot.config import (
    TELEGRAM_SINGLE_MESSAGE_MEDIA_LIMIT,
    TELEGRAM_FILE_UPLOAD_LIMIT,
    TELEGRAM_FILE_UPLOAD_LIMIT_LOCAL_API,
    TEMPLATE_TRANSLATION,
)

environment = JINJA2_ENV
template = environment.get_template("social_media_message.jinja2")
template_text = TEMPLATE_TRANSLATION.get(
    TEMPLATE_LANGUAGE, TEMPLATE_TRANSLATION["zh_CN"]
)


def _get_application():
    """Lazy import to avoid circular dependency."""
    from app.services.telegram_bot import application
    return application


async def send_item_message(
        data: dict, chat_id: Union[int, str] = None, message: Message = None
) -> None:
    """
    :param data: (dict) metadata of the item
    :param chat_id: (int) any chat id for sending
    :param message: (Message) any message to reply
    :return:
    """
    application = _get_application()
    logger.debug(f"send_item_message: {data}, {chat_id}, {message}")
    if not chat_id and not message:
        raise ValueError("must provide chat_id or message")
    if (
            not chat_id
    ) and message:  # this function supports direct reply to a message even if the chat_id is None
        chat_id = message.chat.id
    discussion_chat_id = chat_id
    the_chat = await application.bot.get_chat(chat_id=chat_id)
    logger.debug(f"the chat of sending message: {the_chat}")
    if the_chat.type == "channel" and the_chat.linked_chat_id:
        discussion_chat_id = the_chat.linked_chat_id
    try:
        caption_text = message_formatting(data)
        if len(data["media_files"]) > 0:
            # if the message type is short and there are some media files, send media group
            reply_to_message_id = None
            media_message_group, file_message_group = await media_files_packaging(
                media_files=data["media_files"], data=data
            )
            if (
                    len(media_message_group) > 0
            ):  # if there are some media groups to send, send it
                for i, media_group in enumerate(media_message_group):
                    caption_text = (
                        caption_text
                        if i == 0
                        else f"the {i + 1}th part of the media item:"
                    )
                    logger.debug(f"media group: {media_group}")
                    logger.debug(
                        f"caption text: {caption_text},length={len(caption_text)}"
                    )
                    sent_media_files_message = await application.bot.send_media_group(
                        chat_id=chat_id,
                        media=media_group,
                        parse_mode=ParseMode.HTML,
                        caption=caption_text,
                        write_timeout=TELEBOT_WRITE_TIMEOUT,
                        reply_to_message_id=message.message_id if message else None,
                    )
                    if sent_media_files_message is tuple:
                        reply_to_message_id = sent_media_files_message[0].message_id
                    elif sent_media_files_message is Message:
                        reply_to_message_id = sent_media_files_message.message_id
                    logger.debug(f"sent media files message: {sent_media_files_message}")
            else:
                sent_message = await application.bot.send_message(
                    chat_id=chat_id,
                    text=caption_text,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=message.message_id if message else None,
                    disable_web_page_preview=True
                    if data["message_type"] == MessageType.SHORT
                    else False,
                    disable_notification=True,
                )
            if discussion_chat_id != chat_id:
                await asyncio.sleep(
                    3
                )  # wait for several seconds to avoid missing the target message
                # if the chat is a channel, get the latest pinned message from the channel and reply to it
                group_chat = await application.bot.get_chat(chat_id=discussion_chat_id)
                logger.debug(f"the group chat: {group_chat}")
                pinned_message = group_chat.pinned_message
                logger.debug(f"the pinned message: {pinned_message}")
                if len(media_message_group) > 0:
                    if (
                            pinned_message.forward_origin.message_id
                            == sent_media_files_message[-1].message_id
                    ):
                        reply_to_message_id = (
                                group_chat.pinned_message.id
                                - len(sent_media_files_message)
                                + 1
                        )
                    else:
                        reply_to_message_id = group_chat.pinned_message.id + 1
                elif pinned_message.forward_origin.message_id == sent_message.message_id:
                    reply_to_message_id = group_chat.pinned_message.id
                else:
                    reply_to_message_id = group_chat.pinned_message.id + 1
            if (
                    len(file_message_group) > 0
            ):  # to send files, the files messages should be replied to the message sent before
                logger.debug(f"reply_to_message_id: {reply_to_message_id}")
                for file_group in file_message_group:
                    logger.debug(f"file group: {file_group}")
                    await application.bot.send_media_group(
                        chat_id=discussion_chat_id,
                        media=file_group,
                        reply_to_message_id=reply_to_message_id,
                        parse_mode=ParseMode.HTML,
                        disable_notification=True,
                    )
        else:
            await application.bot.send_message(
                chat_id=chat_id,
                text=caption_text,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.message_id if message else None,
                disable_web_page_preview=True
                if data["message_type"] == "short"
                else False,
                disable_notification=True,
            )
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        await send_debug_channel(traceback.format_exc())


async def send_debug_channel(message: str) -> None:
    from app.config import TELEBOT_DEBUG_CHANNEL
    application = _get_application()
    if TELEBOT_DEBUG_CHANNEL is not None:
        await application.bot.send_message(
            chat_id=TELEBOT_DEBUG_CHANNEL, text=message, parse_mode=ParseMode.HTML
        )


def message_formatting(data: dict) -> str:
    """
    Format the message to be sent to the user.
    :param data:
    :return: text (str) the formatted text for telegram bot api sending message.
    """
    if data["message_type"] == "short":
        data["text"] = telegram_message_html_trim(data["text"])
    message_template = template
    text = message_template.render(data=data, template_text=template_text)
    logger.debug(f"message text: \n{text}")
    return text


async def media_files_packaging(media_files: list, data: dict) -> tuple:
    """
    Download the media files from data["media_files"] and package them into a list of media group or file group for
    sending them by send_media_group method or send_document method.
    :param data: (dict) metadata of the item
    :param media_files: (list) a list of media files,
    :return: (tuple) a tuple of media group and file group
        media_message_group: (list) a list of media items, the type of each item is InputMediaPhoto or InputMediaVideo
        file_group: (list) a list of file items, the type of each item is InputFile
    TODO: It's not a good practice for this function. This method will still download all the media files even when
        media files are too large and it can be memory consuming even if we use a database to store the media files.
        The function should be optimized to resolve the media files one group by one group and send each group
        immediately after it is resolved.
        This processing method should be optimized in the future.
    """
    media_counter, file_counter = 0, 0
    media_message_group, media_group, file_message_group, file_group = [], [], [], []
    for (
            media_item
    ) in media_files:  # To traverse all media items in the media files list
        # check if we need to create a new media group
        if media_counter == TELEGRAM_SINGLE_MESSAGE_MEDIA_LIMIT:
            # the limitation of media item for a single telegram media group message is 10
            media_message_group.append(media_group)
            media_group = []
            media_counter = 0
        if file_counter == TELEGRAM_SINGLE_MESSAGE_MEDIA_LIMIT:
            # the limitation of media item for a single telegram media group message is 10
            file_message_group.append(file_group)
            file_group = []
            file_counter = 0
        if not (
                media_item["media_type"] in ["image", "gif", "video"]
                and data["message_type"] == "long"
        ):
            # check the url validity
            url_parser = urlparse(media_item["url"])
            if url_parser.scheme in [
                "http",
                "https",
            ]:  # if the url is a http url, download the file
                file_format = "mp4" if media_item["media_type"] == "video" else None
                io_object = await download_file_by_metadata_item(
                    media_item["url"], data=data, file_format=file_format
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
                ext = await check_image_type(io_object)
                # jpg to jpeg, ignore case
                if ext.lower() == "jpg":
                    ext = "JPEG"
                io_object.seek(0)
                image = Image.open(io_object, formats=[ext])
                img_width, img_height = image.size
                ratio = float(max(img_height, img_width)) / float(
                    min(img_height, img_width)
                )
                # don't try to resize image if the ratio is too large
                if (
                        ratio < 5
                        or max(img_height, img_width) < TELEGRAM_IMAGE_DIMENSION_LIMIT
                ):
                    image = image_compressing(image, TELEGRAM_IMAGE_DIMENSION_LIMIT)
                    with BytesIO() as buffer:
                        # mime_type file format
                        image.save(buffer, format=ext)
                        buffer.seek(0)
                        resized_ratio = max(image.height, image.width) / min(
                            image.height, image.width
                        )
                        logger.debug(
                            f"resized image size: {buffer.getbuffer().nbytes}, ratio: {resized_ratio}, width: {image.width}, height: {image.height}"
                        )
                        media_group.append(InputMediaPhoto(buffer, filename=filename))
                # the image is not able to get json serialized
                logger.debug(
                    f"image size: {file_size}, ratio: {ratio}, width: {img_width}, height: {img_height}"
                )
                if (
                        file_size > TELEGRAM_IMAGE_SIZE_LIMIT
                        or img_width > TELEGRAM_IMAGE_DIMENSION_LIMIT
                        or img_height > TELEGRAM_IMAGE_DIMENSION_LIMIT
                ) and data["category"] not in ["xiaohongshu"]:
                    io_object = await download_file_by_metadata_item(
                        url=image_url, data=data
                    )
                    if not io_object.name.endswith(".gif"):
                        if not io_object.name.endswith(ext.lower()):
                            io_object.name = io_object.name + "." + ext.lower()
                        # TODO: it is not a good way to judge whether it is a gif...
                        file_group.append(
                            InputMediaDocument(io_object, parse_mode=ParseMode.HTML)
                        )
                        file_counter += 1
            elif media_item["media_type"] == "gif":
                io_object = await download_file_by_metadata_item(
                    url=media_item["url"],
                    data=data,
                    file_name="gif_image-" + str(media_counter) + ".gif",
                )
                io_object.name = io_object.name + ".gif"
                media_group.append(InputMediaAnimation(io_object))
            elif media_item["media_type"] == "video":
                media_group.append(InputMediaVideo(io_object, supports_streaming=True))
            # TODO: not have any services to store audio files for now, just a placeholder
            elif media_item["media_type"] == "audio":
                media_group.append(InputMediaAudio(io_object))
            elif media_item["media_type"] == "document":
                file_group.append(
                    InputMediaDocument(io_object, parse_mode=ParseMode.HTML)
                )
                file_counter += 1
            media_counter += 1
            logger.info(
                f"get the {media_counter}th media item,type: {media_item['media_type']}, url: {media_item['url']}"
            )
    # check if the media group is empty, if it is, return None
    if len(media_group) > 0:  # append the last media group
        media_message_group.append(media_group)
    if len(file_group) > 0:
        file_message_group.append(file_group)
    return media_message_group, file_message_group

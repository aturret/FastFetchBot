from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
)

from fastfetchbot_shared.models.metadata_item import MessageType
from core import api_client
from core.services.message_sender import send_item_message
from fastfetchbot_shared.utils.logger import logger
from core.config import (
    TELEGRAM_CHANNEL_ID,
)


async def buttons_process(update: Update, context: CallbackContext) -> None:
    from core.services.bot_app import application

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
        metadata_item = await api_client.get_item(
            url=data["url"], **extra_args
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
    from core.services.bot_app import application

    choose_channel_keyboard = []
    for i, channel_id in enumerate(TELEGRAM_CHANNEL_ID):
        channel_chat = await application.bot.get_chat(chat_id=channel_id)
        choose_channel_keyboard.append(
            [
                InlineKeyboardButton(
                    channel_chat.title,
                    callback_data={
                        "type": "channel",
                        "url": data["url"],
                        "source": data.get("source"),
                        "content_type": data.get("content_type"),
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
        "Sorry, Error Occurred, I could not process this button click."
    )

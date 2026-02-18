# TODO: Implement Telegram Service
# example: https://docs.python-telegram-bot.org/en/stable/examples.customwebhookbot.html
import mimetypes

mimetypes.init()

from telegram import (
    Update,
    MessageEntity,
)
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    InvalidCallbackData,
    AIORateLimiter,
)

from app.utils.logger import logger
from app.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_WEBHOOK_URL,
    TELEGRAM_BOT_SECRET_TOKEN,
    TELEBOT_API_SERVER,
    TELEBOT_API_SERVER_FILE,
    TELEBOT_LOCAL_FILE_MODE,
    TELEBOT_CONNECT_TIMEOUT,
    TELEBOT_READ_TIMEOUT,
    TELEBOT_WRITE_TIMEOUT,
    TELEBOT_MAX_RETRY,
)

# Re-export for external consumers
from app.services.telegram_bot.message_sender import send_item_message  # noqa: F401
from app.services.telegram_bot.handlers import (  # noqa: F401
    https_url_process,
    https_url_auto_process,
    all_messages_process,
    buttons_process,
    invalid_buttons,
    error_process,
    content_process_function,
)

"""
application and handlers initialization
"""


async def set_webhook() -> bool:
    logger.debug(f"set_webhook: {TELEGRAM_WEBHOOK_URL}, secret_token: {TELEGRAM_BOT_SECRET_TOKEN}")
    return await application.bot.set_webhook(
        url=TELEGRAM_WEBHOOK_URL, secret_token=TELEGRAM_BOT_SECRET_TOKEN
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
        .rate_limiter(AIORateLimiter(max_retries=TELEBOT_MAX_RETRY))
        .build()
    )
else:
    logger.error("TELEGRAM_BOT_TOKEN is not set!")


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
    application.add_error_handler(error_process)
    if application.post_init:
        await application.post_init()
    await application.start()


async def shutdown() -> None:
    await application.stop()
    if application.post_stop:
        await application.post_stop()
    await application.shutdown()
    if application.post_shutdown:
        await application.post_shutdown()


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

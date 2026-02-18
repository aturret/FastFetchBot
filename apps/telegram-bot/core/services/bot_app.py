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

from fastfetchbot_shared.utils.logger import logger
from core.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BOT_MODE,
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

from core.handlers.url_process import https_url_process, https_url_auto_process
from core.handlers.buttons import buttons_process, invalid_buttons
from core.handlers.messages import all_messages_process, error_process

# Re-export for external consumers
from core.services.message_sender import send_item_message  # noqa: F401

"""
application and handlers initialization
"""


async def set_webhook() -> bool:
    logger.debug(f"set_webhook: {TELEGRAM_WEBHOOK_URL}, secret_token: {TELEGRAM_BOT_SECRET_TOKEN}")
    return await application.bot.set_webhook(
        url=TELEGRAM_WEBHOOK_URL, secret_token=TELEGRAM_BOT_SECRET_TOKEN
    )


if TELEGRAM_BOT_TOKEN is not None:
    builder = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .arbitrary_callback_data(True)
        .connect_timeout(TELEBOT_CONNECT_TIMEOUT)
        .read_timeout(TELEBOT_READ_TIMEOUT)
        .write_timeout(TELEBOT_WRITE_TIMEOUT)
        .base_url(TELEBOT_API_SERVER)
        .base_file_url(TELEBOT_API_SERVER_FILE)
        .local_mode(TELEBOT_LOCAL_FILE_MODE)
        .rate_limiter(AIORateLimiter(max_retries=TELEBOT_MAX_RETRY))
    )
    if TELEGRAM_BOT_MODE == "webhook":
        builder = builder.updater(None)
    application = builder.build()
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


async def start_polling() -> None:
    """Start the Updater's polling loop. Only valid when TELEGRAM_BOT_MODE == 'polling'."""
    if application.updater is None:
        raise RuntimeError("Cannot start polling: updater is None (webhook mode?)")
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("Polling started.")


async def show_bot_info() -> None:
    """Display basic status and information for the Telegram bot."""
    try:
        bot = application.bot
        bot_info = await bot.get_me()

        logger.info("=" * 60)
        logger.info("TELEGRAM BOT INFORMATION")
        logger.info("=" * 60)
        logger.info(f"Bot Username: @{bot_info.username}")
        logger.info(f"Bot Name: {bot_info.first_name}")
        logger.info(f"Bot ID: {bot_info.id}")
        logger.info(f"Can Join Groups: {bot_info.can_join_groups}")
        logger.info(f"Can Read All Group Messages: {bot_info.can_read_all_group_messages}")
        logger.info(f"Supports Inline Queries: {bot_info.supports_inline_queries}")
        logger.info(f"Mode: {TELEGRAM_BOT_MODE}")

        if TELEGRAM_BOT_MODE == "webhook":
            webhook_info = await bot.get_webhook_info()
            logger.info(f"Webhook URL: {webhook_info.url}")
            logger.info(f"Webhook Has Custom Certificate: {webhook_info.has_custom_certificate}")
            logger.info(f"Pending Update Count: {webhook_info.pending_update_count}")
            if webhook_info.last_error_date:
                logger.info(f"Last Error Date: {webhook_info.last_error_date}")
                logger.info(f"Last Error Message: {webhook_info.last_error_message}")

        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Error getting bot info: {e}")


async def shutdown() -> None:
    if application.updater and application.updater.running:
        await application.updater.stop()
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

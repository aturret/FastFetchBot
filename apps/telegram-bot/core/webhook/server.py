import asyncio
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.services.bot_app import process_telegram_update
from core.services.message_sender import send_item_message
from core.config import settings
from fastfetchbot_shared.utils.logger import logger


@asynccontextmanager
async def lifespan(app):
    """
    Starlette lifespan context manager.  Runs startup/shutdown inside the
    SAME event loop that uvicorn uses for request handling.  This ensures the
    python-telegram-bot Application's dispatcher, polling updater, and
    update_queue all share one event loop.
    """
    from core.services.bot_app import startup, shutdown, set_webhook, start_polling, show_bot_info
    from fastfetchbot_shared.database import init_db, close_db

    # -- startup --
    if settings.ITEM_DATABASE_ON:
        from core import database
        await database.startup()
    await init_db()
    if settings.TELEGRAM_BOT_TOKEN:
        await startup()
        if settings.TELEGRAM_BOT_MODE == "webhook":
            result = await set_webhook()
            if result:
                logger.info("Webhook registered successfully")
            else:
                logger.error("Failed to register webhook!")
        else:
            await start_polling()
        await show_bot_info()

    yield

    # -- shutdown --
    if settings.TELEGRAM_BOT_TOKEN:
        await shutdown()
    await close_db()
    if settings.ITEM_DATABASE_ON:
        from core import database
        await database.shutdown()


def _log_task_exception(task: asyncio.Task):
    """Callback for fire-and-forget tasks to ensure exceptions are logged."""
    if not task.cancelled() and task.exception():
        logger.exception("Unhandled error in background task", exc_info=task.exception())


async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.TELEGRAM_BOT_SECRET_TOKEN:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        data = await request.json()
    except Exception:
        logger.exception("Failed to parse webhook request body")
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    logger.debug(f"Telegram webhook update received: {data.get('update_id', 'unknown')}")
    task = asyncio.create_task(process_telegram_update(data))
    task.add_done_callback(_log_task_exception)
    return JSONResponse({"status": "ok"})


async def send_message_endpoint(request: Request):
    try:
        data = await request.json()
        metadata_item = data["data"]
        chat_id = data.get("chat_id")
        if isinstance(chat_id, str) and chat_id.startswith("-"):
            chat_id = int(chat_id)
        await send_item_message(metadata_item, chat_id=chat_id)
        return JSONResponse({"status": "ok"})
    except Exception:
        logger.exception("Failed to handle send_message request")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


async def health(request: Request):
    return JSONResponse({"status": "healthy"})


# Full webhook app (used in webhook mode)
webhook_app = Starlette(
    routes=[
        Route("/webhook", telegram_webhook, methods=["POST"]),
        Route("/send_message", send_message_endpoint, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ],
    lifespan=lifespan,
)

# Minimal app (used in polling mode — no /webhook route needed)
callback_app = Starlette(
    routes=[
        Route("/send_message", send_message_endpoint, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ],
    lifespan=lifespan,
)

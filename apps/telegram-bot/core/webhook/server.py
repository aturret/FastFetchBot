import asyncio
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.services.bot_app import process_telegram_update
from core.services.message_sender import send_item_message
from core.config import TELEGRAM_BOT_SECRET_TOKEN
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
    from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_MODE, DATABASE_ON

    # -- startup --
    if DATABASE_ON:
        from core import database
        await database.startup()
    if TELEGRAM_BOT_TOKEN:
        await startup()
        if TELEGRAM_BOT_MODE == "webhook":
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
    if TELEGRAM_BOT_TOKEN:
        await shutdown()
    if DATABASE_ON:
        from core import database
        await database.shutdown()


async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != TELEGRAM_BOT_SECRET_TOKEN:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    data = await request.json()
    logger.debug(f"Telegram webhook update received: {data.get('update_id', 'unknown')}")
    asyncio.create_task(process_telegram_update(data))
    return JSONResponse({"status": "ok"})


async def send_message_endpoint(request: Request):
    data = await request.json()
    metadata_item = data["data"]
    chat_id = data.get("chat_id")
    if isinstance(chat_id, str) and chat_id.startswith("-"):
        chat_id = int(chat_id)
    await send_item_message(metadata_item, chat_id=chat_id)
    return JSONResponse({"status": "ok"})


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

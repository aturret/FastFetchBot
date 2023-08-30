import asyncio
import sentry_sdk

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app import database, auth
from app.routers import telegram_bot
from app.services import telegram_bot as telegram_bot_service
from app.config import TELEGRAM_BOT_TOKEN
from app.utils.logger import logger

SENTRY_DSN = ""

# https://docs.sentry.io/platforms/python/guides/fastapi/
sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production,
    traces_sample_rate=1.0,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_bot_service.startup()
    yield
    await telegram_bot_service.shutdown()


def create_app():
    fastapi_application = FastAPI(lifespan=lifespan)
    if TELEGRAM_BOT_TOKEN is not None:
        fastapi_application.include_router(telegram_bot.router)
    else:
        logger.warning("Telegram bot token not set, telegram bot disabled")
    return fastapi_application


fastapi_application = create_app()

# @fastapi_application.on_event("shutdown")
# async def on_shutdown():
#     # await database.shutdown()
#     await telegram_bot_service.shutdown()

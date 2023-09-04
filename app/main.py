import sentry_sdk
import multiprocessing

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

started = multiprocessing.Value('i', 0)
mutex = multiprocessing.Lock()

@asynccontextmanager
async def lifespan(app: FastAPI):
    mutex.acquire()
    if started.value == 0:
        started.value = 1
        await telegram_bot_service.set_webhook()
    mutex.release()

    await telegram_bot_service.startup()
    yield
    await telegram_bot_service.shutdown()


def create_app():
    fastapi_app = FastAPI(lifespan=lifespan)
    if TELEGRAM_BOT_TOKEN is not None:
        fastapi_app.include_router(telegram_bot.router)
    else:
        logger.warning("Telegram bot token not set, telegram bot disabled")
    return fastapi_app


app = create_app()

# @fastapi_application.on_event("shutdown")
# async def on_shutdown():
#     # await database.shutdown()
#     await telegram_bot_service.shutdown()

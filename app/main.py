import sentry_sdk
import multiprocessing

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware

from app import auth, database
from app.routers import telegram_bot, inoreader
from app.services import telegram_bot as telegram_bot_service
from app.config import TELEGRAM_BOT_TOKEN, DATABASE_ON
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

started = multiprocessing.Value("i", 0)
mutex = multiprocessing.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    mutex.acquire()
    if started.value == 0:
        started.value = 1
        await telegram_bot_service.set_webhook()
    mutex.release()
    if DATABASE_ON:
        await database.startup()
    await telegram_bot_service.startup()
    yield
    if DATABASE_ON:
        await database.shutdown()
    await telegram_bot_service.shutdown()


class LogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        logger.info(f"{request.method} {request.url}")
        response = await call_next(request)
        return response


def create_app():
    fastapi_app = FastAPI(lifespan=lifespan)
    fastapi_app.add_middleware(LogMiddleware)
    if TELEGRAM_BOT_TOKEN is not None:
        fastapi_app.include_router(telegram_bot.router)
    else:
        logger.warning("Telegram bot token not set, telegram bot disabled")
    fastapi_app.include_router(inoreader.router)
    return fastapi_app


app = create_app()

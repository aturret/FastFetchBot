import asyncio
import sentry_sdk

from fastapi import FastAPI

from app import database, auth
from app.routers import telegram_bot
from app.services import telegram_bot as telegram_bot_service

SENTRY_DSN = ""

# https://docs.sentry.io/platforms/python/guides/fastapi/
sentry_sdk.init(
    dsn=SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production,
    traces_sample_rate=1.0,
)

app = FastAPI()
app.include_router(telegram_bot.router)


@app.on_event("startup")
async def on_startup():
    await database.startup()
    await telegram_bot_service.startup()


@app.on_event("shutdown")
async def on_shutdown():
    await database.shutdown()
    await telegram_bot_service.shutdown()

    # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
    await asyncio.sleep(0)

# TODO: Implement Telegram Service
# example: https://docs.python-telegram-bot.org/en/stable/examples.customwebhookbot.html

from telegram.ext import (
    Application,
)
from app.config import *

# TODO: move to config
TELEGRAM_BOT_TOKEN = ""

application = Application.builder().token("TOKEN").updater(None).build()


async def set_webhook(url: str):
    await application.bot.set_webhook(url=url)


async def startup():
    await application.start()


async def shutdown():
    await application.stop()

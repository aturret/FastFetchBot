import os

env = os.environ

# Telegram bot environment variables
TELEGRAM_BOT_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = env.get("BASE_URL", "") + "/telegram_webhook"
import os

env = os.environ

# FastAPI environment variables
BASE_URL = env.get("BASE_URL", "")
PORT = int(env.get("PORT", 10450))
API_KEY_NAME = env.get("API_KEY_NAME", "")
API_KEY = env.get("API_KEY", "")
TELEGRAM_API_KEY = env.get("TELEGRAM_API_KEY", "")

# Telegram bot environment variables
TELEGRAM_BOT_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
channel_id = env.get("CHANNEL_ID", "")
if channel_id.startswith("@"):
    CHANNEL_ID = channel_id
elif channel_id.startswith("-1"):
    CHANNEL_ID = int(channel_id)
else:
    CHANNEL_ID = None
WEBHOOK_URL = "https://" + BASE_URL + "/telegram/bot/webhook"

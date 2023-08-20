import os
import tempfile
from jinja2 import Environment, FileSystemLoader
import gettext

env = os.environ


# FastAPI environment variables
BASE_URL = env.get("BASE_URL", "localhost")
API_KEY_NAME = env.get("API_KEY_NAME", "")
API_KEY = env.get("API_KEY", "")
TELEGRAM_API_KEY = env.get("TELEGRAM_API_KEY", "")

# Logging environment variables
LOG_FILE_PATH = env.get("LOG_FILE_PATH", None)
LOG_LEVEL = env.get("LOG_LEVEL", "DEBUG")

# Telegram bot environment variables
TELEGRAM_BOT_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
telegram_channel_id = env.get("CHANNEL_ID", "")
if telegram_channel_id.startswith("@"):
    TELEGRAM_CHANNEL_ID = telegram_channel_id
elif telegram_channel_id.startswith("-1"):
    TELEGRAM_CHANNEL_ID = int(telegram_channel_id)
else:
    TELEGRAM_CHANNEL_ID = None
TELEGRAM_WEBHOOK_URL = "https://" + BASE_URL + "/telegram/bot/webhook"
TELEBOT_API_SERVER_HOST = env.get("TELEBOT_API_SERVER_HOST", None)
TELEBOT_API_SERVER_PORT = env.get("TELEBOT_API_SERVER_PORT", None)
TELEBOT_API_SERVER = (
    f"http://{TELEBOT_API_SERVER_HOST}:{TELEBOT_API_SERVER_PORT}" + "/bot{0}/{1}"
    if (TELEBOT_API_SERVER_HOST and TELEBOT_API_SERVER_PORT)
    else "https://api.telegram.org/bot"
)
TELEGRAM_IMAGE_DIMENSION_LIMIT = env.get("TELEGRAM_IMAGE_SIZE_LIMIT", None)
TELEGRAM_IMAGE_DIMENSION_LIMIT = (
    int(TELEGRAM_IMAGE_DIMENSION_LIMIT) if TELEGRAM_IMAGE_DIMENSION_LIMIT else 1600
)
TELEGRAM_IMAGE_SIZE_LIMIT = env.get("TELEGRAM_IMAGE_SIZE_LIMIT", None)
TELEGRAM_IMAGE_SIZE_LIMIT = (
    int(TELEGRAM_IMAGE_SIZE_LIMIT) if TELEGRAM_IMAGE_SIZE_LIMIT else 5242880
)

# MongoDB environment variables
MONGODB_PORT = int(env.get("MONGODB_PORT")) if env.get("MONGODB_PORT") else 27017
MONGODB_HOST = env.get("MONGODB_HOST", "localhost")
MONGODB_URL = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}"


# Filesystem environment variables
TEMP_DIR = env.get("TEMP_DIR", tempfile.gettempdir())
WORK_DIR = env.get("WORK_DIR", os.getcwd())


# Services environment variables
JINJA2_ENV = Environment(
    loader=FileSystemLoader("app/templates/"), lstrip_blocks=True, trim_blocks=True
)
X_RAPIDAPI_KEY = env.get("X_RAPIDAPI_KEY", None)


# Open AI API environment variables
OPENAI_API_KEY = env.get("OPENAI_API_KEY", None)


# Locale environment variables
localedir = os.path.join(os.path.dirname(__file__), "locale")
translation = gettext.translation("messages", localedir=localedir, fallback=True)
_ = translation.gettext


# Utils environment variables
HTTP_REQUEST_TIMEOUT = env.get("HTTP_REQUEST_TIMEOUT", 30)

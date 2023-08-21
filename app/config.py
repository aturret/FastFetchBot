import os
import tempfile
import socket
from jinja2 import Environment, FileSystemLoader
import gettext

env = os.environ


def get_env_bool(var_name, default=False):
    """Retrieve environment variable as a boolean."""
    true_values = {'true', '1', 'yes', 'on'}
    false_values = {'false', '0', 'no', 'off'}

    value = env.get(var_name, '').lower()

    if value in true_values:
        return True
    elif value in false_values:
        return False
    else:
        return default


# FastAPI environment variables
BASE_URL = env.get("BASE_URL", "localhost")
API_KEY_NAME = env.get("API_KEY_NAME", "")
API_KEY = env.get("API_KEY", "")
TELEGRAM_API_KEY = env.get("TELEGRAM_API_KEY", "")

# Filesystem environment variables
TEMP_DIR = env.get("TEMP_DIR", tempfile.gettempdir())
WORK_DIR = env.get("WORK_DIR", os.getcwd())
DOWNLOAD_DIR = env.get("DOWNLOAD_DIR", os.path.join(WORK_DIR, "download"))

# Logging environment variables
LOG_FILE_PATH = env.get("LOG_FILE_PATH", TEMP_DIR)
LOG_LEVEL = env.get("LOG_LEVEL", "DEBUG")

# MongoDB environment variables
DATABASE_ON = get_env_bool("DATABASE_ON", False)
MONGODB_PORT = int(env.get("MONGODB_PORT")) if env.get("MONGODB_PORT") else 27017
MONGODB_HOST = env.get("MONGODB_HOST", "localhost")
MONGODB_URL = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}"

# Telegram bot environment variables
TELEGRAM_BOT_TOKEN = env.get("TELEGRAM_BOT_TOKEN", None)
telegram_channel_id = env.get("CHANNEL_ID", "")
if telegram_channel_id.startswith("@"):
    TELEGRAM_CHANNEL_ID = telegram_channel_id
elif telegram_channel_id.startswith("-1"):
    TELEGRAM_CHANNEL_ID = int(telegram_channel_id)
else:
    TELEGRAM_CHANNEL_ID = None
TELEGRAM_WEBHOOK_URL = "https://" + BASE_URL + "/telegram/bot/webhook"
TELEBOT_API_SERVER_HOST = env.get("TELEBOT_API_SERVER_HOST", None)
if TELEBOT_API_SERVER_HOST:
    TELEBOT_API_SERVER_HOST = socket.gethostbyname(TELEBOT_API_SERVER_HOST)
TELEBOT_API_SERVER_PORT = env.get("TELEBOT_API_SERVER_PORT", None)
TELEBOT_API_SERVER = (
    f"http://{TELEBOT_API_SERVER_HOST}:{TELEBOT_API_SERVER_PORT}" + "/bot{0}/{1}"
    if (TELEBOT_API_SERVER_HOST and TELEBOT_API_SERVER_PORT)
    else "https://api.telegram.org/bot"
)
TELEBOT_API_SERVER_FILE = (
    f"http://{TELEBOT_API_SERVER_HOST}:{TELEBOT_API_SERVER_PORT}" + "/file/bot{0}/{1}"
    if (TELEBOT_API_SERVER_HOST and TELEBOT_API_SERVER_PORT)
    else "https://api.telegram.org/file/bot"
)
LOCAL_FILE_MODE = False if TELEBOT_API_SERVER == "https://api.telegram.org/bot" else True
TELEGRAM_IMAGE_DIMENSION_LIMIT = env.get("TELEGRAM_IMAGE_SIZE_LIMIT", None)
TELEGRAM_IMAGE_DIMENSION_LIMIT = (
    int(TELEGRAM_IMAGE_DIMENSION_LIMIT) if TELEGRAM_IMAGE_DIMENSION_LIMIT else 1600
)
TELEGRAM_IMAGE_SIZE_LIMIT = env.get("TELEGRAM_IMAGE_SIZE_LIMIT", None)
TELEGRAM_IMAGE_SIZE_LIMIT = (
    int(TELEGRAM_IMAGE_SIZE_LIMIT) if TELEGRAM_IMAGE_SIZE_LIMIT else 5242880
)

# Youtube-dl environment variables
YOUTUBE_DL_HOST = env.get("YOUTUBE_DL_HOST", "fast-yt-downloader")
YOUTUBE_DL_PORT = env.get("YOUTUBE_DL_PORT", "4000")
YOUTUBE_DL_URL = f"http://{YOUTUBE_DL_HOST}:{YOUTUBE_DL_PORT}"
DOWNLOAD_VIDEO_TIMEOUT = env.get("DOWNLOAD_VIDEO_TIMEOUT", 600)

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

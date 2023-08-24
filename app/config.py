import os
import tempfile
import socket
from jinja2 import Environment, FileSystemLoader
import gettext
import secrets

env = os.environ
current_directory = os.path.dirname(os.path.abspath(__file__))


def get_env_bool(var_name, default=False):
    """Retrieve environment variable as a boolean."""
    true_values = {"true", "1", "yes", "on"}
    false_values = {"false", "0", "no", "off"}

    value = env.get(var_name, "").lower()

    if value in true_values:
        return True
    elif value in false_values:
        return False
    else:
        return default


# FastAPI environment variables
BASE_URL = env.get("BASE_URL", "localhost")
API_KEY_NAME = env.get("API_KEY_NAME", "pwd")
API_KEY = env.get("API_KEY", "")
TELEGRAM_API_KEY = env.get("TELEGRAM_API_KEY", secrets.token_urlsafe(32))

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
telegram_channel_id = env.get("TELEGRAM_CHANNEL_ID", "")
if telegram_channel_id.startswith("@"):
    TELEGRAM_CHANNEL_ID = telegram_channel_id
elif telegram_channel_id.startswith("-1"):
    TELEGRAM_CHANNEL_ID = int(telegram_channel_id)
else:
    TELEGRAM_CHANNEL_ID = None
telebot_debug_channel = env.get("TELEBOT_DEBUG_CHANNEL", "")
if telebot_debug_channel.startswith("@"):
    TELEBOT_DEBUG_CHANNEL = telebot_debug_channel
elif telebot_debug_channel.startswith("-1"):
    TELEBOT_DEBUG_CHANNEL = int(telebot_debug_channel)
else:
    TELEBOT_DEBUG_CHANNEL = None
telegram_channel_admin_list = env.get("TELEGRAM_CHANNEL_ADMIN_LIST", "")
TELEGRAM_CHANNEL_ADMIN_LIST = [
    admin_id for admin_id in telegram_channel_admin_list.split(",")
]
if not TELEGRAM_CHANNEL_ADMIN_LIST:
    TELEGRAM_CHANNEL_ADMIN_LIST = None
TELEGRAM_WEBHOOK_URL = f"https://{BASE_URL}/telegram/bot/webhook?{API_KEY_NAME}={API_KEY}"
TELEBOT_API_SERVER_HOST = env.get("TELEBOT_API_SERVER_HOST", None)
TELEBOT_API_SERVER_PORT = env.get("TELEBOT_API_SERVER_PORT", None)
TELEBOT_API_SERVER = (
    f"http://{TELEBOT_API_SERVER_HOST}:{TELEBOT_API_SERVER_PORT}" + "/bot"
    if (TELEBOT_API_SERVER_HOST and TELEBOT_API_SERVER_PORT)
    else "https://api.telegram.org/bot"
)
TELEBOT_API_SERVER_FILE = (
    f"http://{TELEBOT_API_SERVER_HOST}:{TELEBOT_API_SERVER_PORT}" + "/file/bot"
    if (TELEBOT_API_SERVER_HOST and TELEBOT_API_SERVER_PORT)
    else "https://api.telegram.org/file/bot"
)
TELEBOT_LOCAL_FILE_MODE = (
    False if TELEBOT_API_SERVER == "https://api.telegram.org/bot" else True
)
TELEBOT_CONNECT_TIMEOUT = env.get("TELEGRAM_CONNECT_TIMEOUT", 15)
TELEBOT_READ_TIMEOUT = env.get("TELEGRAM_READ_TIMEOUT", 30)
TELEBOT_WRITE_TIMEOUT = env.get("TELEGRAM_WRITE_TIMEOUT", 15)
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
templates_directory = os.path.join(current_directory, "templates")
JINJA2_ENV = Environment(
    loader=FileSystemLoader(templates_directory), lstrip_blocks=True, trim_blocks=True
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

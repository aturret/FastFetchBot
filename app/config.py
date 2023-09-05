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
    true_values = {"True", "true", "1", "yes", "on"}
    false_values = {"False", "false", "0", "no", "off"}

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
API_KEY = env.get("API_KEY", secrets.token_urlsafe(32))

# Filesystem environment variables
TEMP_DIR = env.get("TEMP_DIR", tempfile.gettempdir())
WORK_DIR = env.get("WORK_DIR", os.getcwd())
DOWNLOAD_DIR = env.get("DOWNLOAD_DIR", os.path.join(WORK_DIR, "download"))
DEBUG_MODE = get_env_bool("DEBUG_MODE", False)

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
TELEGRAM_BOT_SECRET_TOKEN = env.get(
    "TELEGRAM_BOT_SECRET_TOKEN", secrets.token_urlsafe(32)
)
TELEGRAM_CHANNEL_ID = []
telegram_channel_id = env.get("TELEGRAM_CHANNEL_ID", "").split(",")
for single_telegram_channel_id in telegram_channel_id:
    if single_telegram_channel_id.startswith("@"):
        TELEGRAM_CHANNEL_ID.append(single_telegram_channel_id)
    elif single_telegram_channel_id.startswith("-1"):
        TELEGRAM_CHANNEL_ID.append(int(single_telegram_channel_id))
if len(TELEGRAM_CHANNEL_ID) == 0:
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
TELEGRAM_WEBHOOK_URL = f"https://{BASE_URL}/telegram/bot/webhook"
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
FILE_EXPORTER_HOST = env.get("FILE_EXPORTER_HOST", "fast-yt-downloader")
FILE_EXPORTER_PORT = env.get("FILE_EXPORTER_PORT", "4000")
FILE_EXPORTER_URL = f"http://{FILE_EXPORTER_HOST}:{FILE_EXPORTER_PORT}"
DOWNLOAD_VIDEO_TIMEOUT = env.get("DOWNLOAD_VIDEO_TIMEOUT", 600)

# Services environment variables
templates_directory = os.path.join(current_directory, "templates")
JINJA2_ENV = Environment(
    loader=FileSystemLoader(templates_directory), lstrip_blocks=True, trim_blocks=True
)
X_RAPIDAPI_KEY = env.get("X_RAPIDAPI_KEY", None)
TWITTER_EMAIL = env.get("TWITTER_EMAIL", None)
TWITTER_PASSWORD = env.get("TWITTER_PASSWORD", None)
TWITTER_USERNAME = env.get("TWITTER_USERNAME", None)
TWITTER_CT0 = env.get("TWITTER_CT0", None)
TWITTER_AUTH_TOKEN = env.get("TWITTER_AUTH_TOKEN", None)
TWITTER_COOKIES = {
    "ct0": TWITTER_CT0,
    "auth_token": TWITTER_AUTH_TOKEN,
}
XIAOHONGSHU_A1 = env.get("XIAOHONGSHU_A1", None)
XIAOHONGSHU_WEBID = env.get("XIAOHONGSHU_WEBID", None)
XIAOHONGSHU_WEBSESSION = env.get("XIAOHONGSHU_WEBSESSION", None)
XIAOHONGSHU_COOKIES = {
    "a1": XIAOHONGSHU_A1,
    "web_id": XIAOHONGSHU_WEBID,
    "web_session": XIAOHONGSHU_WEBSESSION,
}
AWS_ACCESS_KEY_ID = env.get("AWS_ACCESS_KEY_ID", None)
AWS_SECRET_ACCESS_KEY = env.get("AWS_SECRET_ACCESS_KEY", None)
AWS_S3_BUCKET_NAME = env.get("AWS_S3_BUCKET_NAME", "")
AWS_REGION_NAME = env.get("AWS_REGION_NAME", "")
AWS_DOMAIN_HOST = env.get("AWS_DOMAIN_HOST", None)

# Open AI API environment variables
OPENAI_API_KEY = env.get("OPENAI_API_KEY", None)

# Locale environment variables
localedir = os.path.join(os.path.dirname(__file__), "locale")
translation = gettext.translation("messages", localedir=localedir, fallback=True)
_ = translation.gettext

# Utils environment variables
HTTP_REQUEST_TIMEOUT = env.get("HTTP_REQUEST_TIMEOUT", 30)

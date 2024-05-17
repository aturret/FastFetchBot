import os
import tempfile

from jinja2 import Environment, FileSystemLoader
import gettext
import secrets

from app.utils.parse import get_env_bool

env = os.environ
current_directory = os.path.dirname(os.path.abspath(__file__))

# FastAPI environment variables
BASE_URL = env.get("BASE_URL", "localhost")
API_KEY_NAME = env.get("API_KEY_NAME", "pwd")
API_KEY = env.get("API_KEY", secrets.token_urlsafe(32))

# Filesystem environment variables
TEMP_DIR = env.get("TEMP_DIR", tempfile.gettempdir())
WORK_DIR = env.get("WORK_DIR", os.getcwd())
DOWNLOAD_DIR = env.get("DOWNLOAD_DIR", os.path.join(WORK_DIR, "download"))
DEBUG_MODE = get_env_bool(env, "DEBUG_MODE", False)

# Logging environment variables
LOG_FILE_PATH = env.get("LOG_FILE_PATH", TEMP_DIR)
LOG_LEVEL = env.get("LOG_LEVEL", "DEBUG")

# MongoDB environment variables
DATABASE_ON = get_env_bool(env, "DATABASE_ON", False)
MONGODB_PORT = int(env.get("MONGODB_PORT", 27017)) or 27017
MONGODB_HOST = env.get("MONGODB_HOST", "localhost")
MONGODB_URL = env.get("MONGODB_URL", f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}")

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
TELEBOT_CONNECT_TIMEOUT = int(env.get("TELEGRAM_CONNECT_TIMEOUT", 15)) or 15
TELEBOT_READ_TIMEOUT = int(env.get("TELEGRAM_READ_TIMEOUT", 60)) or 60
TELEBOT_WRITE_TIMEOUT = int(env.get("TELEGRAM_WRITE_TIMEOUT", 60)) or 60
TELEGRAM_IMAGE_DIMENSION_LIMIT = int(env.get("TELEGRAM_IMAGE_SIZE_LIMIT", 1600)) or 1600
TELEGRAM_IMAGE_SIZE_LIMIT = (
    int(env.get("TELEGRAM_IMAGE_SIZE_LIMIT", 5242880)) or 5242880
)
telegram_group_message_ban_list = env.get("TELEGRAM_GROUP_MESSAGE_BAN_LIST", "")
telegram_bot_message_ban_list = env.get("TELEGRAM_BOT_MESSAGE_BAN_LIST", "")


def ban_list_resolver(ban_list_string: str) -> list:
    ban_list = ban_list_string.split(",")
    for item in ban_list:
        if item == "social_media":
            ban_list.extend(
                [
                    "weibo",
                    "twitter",
                    "instagram",
                    "zhihu",
                    "douban",
                    "wechat",
                    "xiaohongshu",
                    "reddit",
                ]
            )
        elif item == "video":
            ban_list.extend(["youtube", "bilibili"])
    return ban_list


TELEGRAM_GROUP_MESSAGE_BAN_LIST = ban_list_resolver(telegram_group_message_ban_list)
TELEGRAM_BOT_MESSAGE_BAN_LIST = ban_list_resolver(telegram_bot_message_ban_list)
telegraph_token_list = env.get("TELEGRAPH_TOKEN_LIST", "")
TELEGRAPH_TOKEN_LIST = telegraph_token_list.split(",") if telegraph_token_list else None

# Youtube-dl environment variables
FILE_EXPORTER_ON = get_env_bool(env, "FILE_EXPORTER_ON", True)
FILE_EXPORTER_HOST = env.get("FILE_EXPORTER_HOST", "fast-yt-downloader")
FILE_EXPORTER_PORT = env.get("FILE_EXPORTER_PORT", "4000")
FILE_EXPORTER_URL = f"http://{FILE_EXPORTER_HOST}:{FILE_EXPORTER_PORT}"
DOWNLOAD_VIDEO_TIMEOUT = env.get("DOWNLOAD_VIDEO_TIMEOUT", 600)

# Services environment variables
templates_directory = os.path.join(current_directory, "templates")
JINJA2_ENV = Environment(
    loader=FileSystemLoader(templates_directory), lstrip_blocks=True, trim_blocks=True
)
TEMPLATE_LANGUAGE = env.get(
    "TEMPLATE_LANGUAGE", "zh_CN"
)  # It is a workaround for translation system

# X-RapidAPI (for instagram)
X_RAPIDAPI_KEY = env.get("X_RAPIDAPI_KEY", None)

# Twitter
TWITTER_EMAIL = env.get("TWITTER_EMAIL", None)
TWITTER_PASSWORD = env.get("TWITTER_PASSWORD", None)
TWITTER_USERNAME = env.get("TWITTER_USERNAME", None)
TWITTER_CT0 = env.get("TWITTER_CT0", None)
TWITTER_AUTH_TOKEN = env.get("TWITTER_AUTH_TOKEN", None)
TWITTER_COOKIES = {
    "ct0": TWITTER_CT0,
    "auth_token": TWITTER_AUTH_TOKEN,
}

# Weibo
WEIBO_COOKIES = env.get("WEIBO_COOKIES", None)

# Xiaohongshu
XIAOHONGSHU_A1 = env.get("XIAOHONGSHU_A1", None)
XIAOHONGSHU_WEBID = env.get("XIAOHONGSHU_WEBID", None)
XIAOHONGSHU_WEBSESSION = env.get("XIAOHONGSHU_WEBSESSION", None)
XIAOHONGSHU_COOKIES = {
    "a1": XIAOHONGSHU_A1,
    "web_id": XIAOHONGSHU_WEBID,
    "web_session": XIAOHONGSHU_WEBSESSION,
}
XHS_PHONE_LIST = env.get("XHS_PHONE_LIST", "").split(",")
XHS_IP_PROXY_LIST = env.get("XHS_IP_PROXY_LIST", "").split(",")
XHS_ENABLE_IP_PROXY = get_env_bool(env, "XHS_ENABLE_IP_PROXY", False)
XHS_SAVE_LOGIN_STATE = get_env_bool(env, "XHS_SAVE_LOGIN_STATE", True)

# Reddit
REDDIT_CLIENT_ID = env.get("REDDIT_CLIENT_ID", None)
REDDIT_CLIENT_SECRET = env.get("REDDIT_CLIENT_SECRET", None)
REDDIT_PASSWORD = env.get("REDDIT_PASSWORD", None)
REDDIT_USERNAME = env.get("REDDIT_USERNAME", None)

# AWS storage
AWS_STORAGE_ON = get_env_bool(env, "AWS_STORAGE_ON", False)
AWS_ACCESS_KEY_ID = env.get("AWS_ACCESS_KEY_ID", None)
AWS_SECRET_ACCESS_KEY = env.get("AWS_SECRET_ACCESS_KEY", None)
AWS_S3_BUCKET_NAME = env.get("AWS_S3_BUCKET_NAME", "")
AWS_REGION_NAME = env.get("AWS_REGION_NAME", "")
AWS_DOMAIN_HOST = env.get("AWS_DOMAIN_HOST", None)
if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_S3_BUCKET_NAME):
    AWS_STORAGE_ON = False
INOREADER_APP_ID = env.get("INOREADER_APP_ID", None)
INOREADER_APP_KEY = env.get("INOREADER_APP_KEY", None)
INOREADER_EMAIL = env.get("INOREADER_EMAIL", None)
INOREADER_PASSWORD = env.get("INOREADER_PASSWORD", None)

# Open AI API environment variables
OPENAI_API_KEY = env.get("OPENAI_API_KEY", None)

# Locale environment variables
localedir = os.path.join(os.path.dirname(__file__), "locale")
translation = gettext.translation("messages", localedir=localedir, fallback=True)
_ = translation.gettext

# Utils environment variables
HTTP_REQUEST_TIMEOUT = env.get("HTTP_REQUEST_TIMEOUT", 30)

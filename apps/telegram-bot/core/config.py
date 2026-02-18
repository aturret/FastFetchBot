import os
import secrets

from jinja2 import Environment, FileSystemLoader

from fastfetchbot_shared.utils.parse import get_env_bool

env = os.environ
current_directory = os.path.dirname(os.path.abspath(__file__))

# API Server connection (for calling the FastFetchBot API server)
API_SERVER_URL = env.get("API_SERVER_URL", "http://localhost:10450")
API_KEY_NAME = env.get("API_KEY_NAME", "pwd")
API_KEY = env.get("API_KEY", secrets.token_urlsafe(32))

# Bot's own BASE_URL (for webhook registration)
BASE_URL = env.get("BASE_URL", "localhost")

# Telegram bot environment variables
TELEGRAM_BOT_ON = get_env_bool(env, "TELEGRAM_BOT_ON", True)
TELEGRAM_BOT_MODE = env.get("TELEGRAM_BOT_MODE", "polling")
TELEGRAM_BOT_TOKEN = env.get("TELEGRAM_BOT_TOKEN", None)
TELEGRAM_BOT_SECRET_TOKEN = env.get(
    "TELEGRAM_BOT_SECRET_TOKEN", secrets.token_urlsafe(32)
)

# Telegram channel configuration
TELEGRAM_CHANNEL_ID = []
telegram_channel_id = env.get("TELEGRAM_CHANNEL_ID", "").split(",")
for single_telegram_channel_id in telegram_channel_id:
    if single_telegram_channel_id.startswith("@"):
        TELEGRAM_CHANNEL_ID.append(single_telegram_channel_id)
    elif single_telegram_channel_id.startswith("-1"):
        TELEGRAM_CHANNEL_ID.append(int(single_telegram_channel_id))
if len(TELEGRAM_CHANNEL_ID) == 0:
    TELEGRAM_CHANNEL_ID = None

# Debug channel
telebot_debug_channel = env.get("TELEBOT_DEBUG_CHANNEL", "")
if telebot_debug_channel.startswith("@"):
    TELEBOT_DEBUG_CHANNEL = telebot_debug_channel
elif telebot_debug_channel.startswith("-1"):
    TELEBOT_DEBUG_CHANNEL = int(telebot_debug_channel)
else:
    TELEBOT_DEBUG_CHANNEL = None

# Channel admin list
telegram_channel_admin_list = env.get("TELEGRAM_CHANNEL_ADMIN_LIST", "")
TELEGRAM_CHANNEL_ADMIN_LIST = [
    admin_id for admin_id in telegram_channel_admin_list.split(",")
]
if not TELEGRAM_CHANNEL_ADMIN_LIST:
    TELEGRAM_CHANNEL_ADMIN_LIST = None

# Webhook URL (constructed from bot's own BASE_URL)
TELEGRAM_WEBHOOK_URL = f"https://{BASE_URL}/webhook"

# Telegram Bot API server configuration
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

# Telegram Bot timeouts
TELEBOT_CONNECT_TIMEOUT = int(env.get("TELEGRAM_CONNECT_TIMEOUT", 15)) or 15
TELEBOT_READ_TIMEOUT = int(env.get("TELEGRAM_READ_TIMEOUT", 60)) or 60
TELEBOT_WRITE_TIMEOUT = int(env.get("TELEGRAM_WRITE_TIMEOUT", 60)) or 60
TELEBOT_MAX_RETRY = int(env.get("TELEGRAM_MAX_RETRY", 5)) or 5

# Telegram image limits
TELEGRAM_IMAGE_DIMENSION_LIMIT = int(env.get("TELEGRAM_IMAGE_SIZE_LIMIT", 1600)) or 1600
TELEGRAM_IMAGE_SIZE_LIMIT = (
    int(env.get("TELEGRAM_IMAGE_SIZE_LIMIT", 5242880)) or 5242880
)

# Ban lists
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

# Feature flags (needed for handler logic)
FILE_EXPORTER_ON = get_env_bool(env, "FILE_EXPORTER_ON", True)
OPENAI_API_KEY = env.get("OPENAI_API_KEY", None)
GENERAL_SCRAPING_ON = get_env_bool(env, "GENERAL_SCRAPING_ON", False)

# Database configuration
DATABASE_ON = get_env_bool(env, "DATABASE_ON", False)
MONGODB_PORT = int(env.get("MONGODB_PORT", 27017)) or 27017
MONGODB_HOST = env.get("MONGODB_HOST", "localhost")
MONGODB_URL = env.get("MONGODB_URL", f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}")

# Jinja2 template configuration
templates_directory = os.path.join(current_directory, "templates")
JINJA2_ENV = Environment(
    loader=FileSystemLoader(templates_directory), lstrip_blocks=True, trim_blocks=True
)

# Template language
TEMPLATE_LANGUAGE = env.get(
    "TEMPLATE_LANGUAGE", "zh_CN"
)  # It is a workaround for translation system

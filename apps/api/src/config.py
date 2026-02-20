import json
import os
import tempfile

from jinja2 import Environment, FileSystemLoader
import gettext
import secrets

from fastfetchbot_shared.utils.parse import get_env_bool

env = os.environ
current_directory = os.path.dirname(os.path.abspath(__file__))
conf_dir = os.path.join(current_directory, "..", "conf")

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

# Telegraph
telegraph_token_list = env.get("TELEGRAPH_TOKEN_LIST", "")
TELEGRAPH_TOKEN_LIST = telegraph_token_list.split(",") if telegraph_token_list else None

# File exporter toggle (used by telegram bot to show/hide buttons)
FILE_EXPORTER_ON = get_env_bool(env, "FILE_EXPORTER_ON", True)
DOWNLOAD_VIDEO_TIMEOUT = env.get("DOWNLOAD_VIDEO_TIMEOUT", 600)

# Celery configuration
CELERY_BROKER_URL = env.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

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

# Bluesky
BLUESKY_USERNAME = env.get("BLUESKY_USERNAME", None)
BLUESKY_PASSWORD = env.get("BLUESKY_PASSWORD", None)

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

# Zhihu
FXZHIHU_HOST = env.get("FXZHIHU_HOST", "fxzhihu.com")

zhihu_cookie_path = os.path.join(conf_dir, "zhihu_cookies.json")
if os.path.exists(zhihu_cookie_path):
    try:
        with open(zhihu_cookie_path, "r") as f:
            ZHIHU_COOKIES_JSON = json.load(f)
    except json.JSONDecodeError:
        print("Error: The file is not in a valid JSON format.")
        ZHIHU_COOKIES_JSON = None
    except FileNotFoundError:
        print("Error: The file does not exist.")
        ZHIHU_COOKIES_JSON = None
else:
    print("Error: We cannot find it.")
    ZHIHU_COOKIES_JSON = None

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

# Open AI API
OPENAI_API_KEY = env.get("OPENAI_API_KEY", None)

# General webpage scraping
GENERAL_SCRAPING_ON = get_env_bool(env, "GENERAL_SCRAPING_ON", False)
GENERAL_SCRAPING_API = env.get("GENERAL_SCRAPING_API", "FIRECRAWL")

# Firecrawl API
FIRECRAWL_API_URL = os.getenv("FIRECRAWL_API_URL", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_WAIT_FOR = int(env.get("FIRECRAWL_WAIT_FOR", 3000))  # milliseconds to wait for JS rendering


# Zyte API
ZYTE_API_KEY = env.get("ZYTE_API_KEY", None)

# Locale directories environment variables
localedir = os.path.join(os.path.dirname(__file__), "locale")
translation = gettext.translation("messages", localedir=localedir, fallback=True)
_ = translation.gettext

# Utils environment variables
HTTP_REQUEST_TIMEOUT = env.get("HTTP_REQUEST_TIMEOUT", 30)

# Telegram Bot callback URL (for inter-service communication)
TELEGRAM_BOT_CALLBACK_URL = env.get("TELEGRAM_BOT_CALLBACK_URL", "http://telegram-bot:10451")

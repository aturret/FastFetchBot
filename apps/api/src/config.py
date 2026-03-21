import os
import tempfile
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

# File exporter toggle (used by telegram bot to show/hide buttons)
FILE_EXPORTER_ON = get_env_bool(env, "FILE_EXPORTER_ON", True)
DOWNLOAD_VIDEO_TIMEOUT = env.get("DOWNLOAD_VIDEO_TIMEOUT", 600)

# Celery configuration
CELERY_BROKER_URL = env.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# AWS storage
AWS_STORAGE_ON = get_env_bool(env, "AWS_STORAGE_ON", False)
AWS_ACCESS_KEY_ID = env.get("AWS_ACCESS_KEY_ID", None)
AWS_SECRET_ACCESS_KEY = env.get("AWS_SECRET_ACCESS_KEY", None)
AWS_S3_BUCKET_NAME = env.get("AWS_S3_BUCKET_NAME", "")
AWS_REGION_NAME = env.get("AWS_REGION_NAME", "")
AWS_DOMAIN_HOST = env.get("AWS_DOMAIN_HOST", None)
if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_S3_BUCKET_NAME):
    AWS_STORAGE_ON = False

# Inoreader
INOREADER_APP_ID = env.get("INOREADER_APP_ID", None)
INOREADER_APP_KEY = env.get("INOREADER_APP_KEY", None)
INOREADER_EMAIL = env.get("INOREADER_EMAIL", None)
INOREADER_PASSWORD = env.get("INOREADER_PASSWORD", None)

# Locale directories environment variables
localedir = os.path.join(os.path.dirname(__file__), "locale")
translation = gettext.translation("messages", localedir=localedir, fallback=True)
_ = translation.gettext

# Utils environment variables
HTTP_REQUEST_TIMEOUT = env.get("HTTP_REQUEST_TIMEOUT", 30)

# Telegram Bot callback URL (for inter-service communication)
TELEGRAM_BOT_CALLBACK_URL = env.get("TELEGRAM_BOT_CALLBACK_URL", "http://telegram-bot:10451")

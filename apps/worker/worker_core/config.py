import os

from fastfetchbot_shared.utils.parse import get_env_bool

env = os.environ

current_directory = os.path.dirname(os.path.abspath(__file__))
conf_dir = os.path.join(current_directory, "..", "conf")

CELERY_BROKER_URL = env.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Conf directory: defaults to apps/worker/conf/ (same convention as API's apps/api/conf/)
# In Docker, override via CONF_DIR env var to /app/conf (where the volume is mounted)
CONF_DIR = env.get("CONF_DIR", conf_dir)

# File export config
DOWNLOAD_DIR = env.get("DOWNLOAD_DIR", "/tmp")
COOKIE_FILE_PATH = env.get("COOKIE_FILE_PATH", os.path.join(CONF_DIR, "cookies.txt"))
PROXY_MODE = get_env_bool(env, "PROXY_MODE", False)
PROXY_URL = env.get("PROXY_URL", "")
YOUTUBE_COOKIE = get_env_bool(env, "YOUTUBE_COOKIE", False)
BILIBILI_COOKIE = get_env_bool(env, "BILIBILI_COOKIE", False)
OPENAI_API_KEY = env.get("OPENAI_API_KEY", "")

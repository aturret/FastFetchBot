import os

from fastfetchbot_shared.utils.parse import get_env_bool

env = os.environ

# ARQ Redis (task queue)
ARQ_REDIS_URL = env.get("ARQ_REDIS_URL", "redis://localhost:6379/2")

# Outbox Redis (result delivery)
OUTBOX_REDIS_URL = env.get("OUTBOX_REDIS_URL", "redis://localhost:6379/3")
OUTBOX_QUEUE_KEY = env.get("OUTBOX_QUEUE_KEY", "scrape:outbox")

# Celery (for PDF export tasks on existing worker)
CELERY_BROKER_URL = env.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Feature flags
STORE_TELEGRAPH = get_env_bool(env, "STORE_TELEGRAPH", True)
STORE_DOCUMENT = get_env_bool(env, "STORE_DOCUMENT", False)
DATABASE_ON = get_env_bool(env, "DATABASE_ON", False)

# MongoDB (optional, for DB storage)
MONGODB_HOST = env.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(env.get("MONGODB_PORT", 27017))
MONGODB_URL = env.get("MONGODB_URL", f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}")

# Download timeout for Celery PDF tasks
DOWNLOAD_VIDEO_TIMEOUT = int(env.get("DOWNLOAD_VIDEO_TIMEOUT", 600))

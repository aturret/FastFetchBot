import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AsyncWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # ARQ Redis
    ARQ_REDIS_URL: str = "redis://localhost:6379/2"

    # Outbox Redis
    OUTBOX_REDIS_URL: str = "redis://localhost:6379/3"
    OUTBOX_QUEUE_KEY: str = "scrape:outbox"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Feature flags
    STORE_TELEGRAPH: bool = True
    STORE_DOCUMENT: bool = False
    DATABASE_ON: bool = False

    # MongoDB
    MONGODB_HOST: str = "localhost"
    MONGODB_PORT: int = 27017
    MONGODB_URL: str = ""

    # Timeout
    DOWNLOAD_VIDEO_TIMEOUT: int = 600

    @model_validator(mode="after")
    def _resolve_derived(self) -> "AsyncWorkerSettings":
        if not self.MONGODB_URL:
            self.MONGODB_URL = f"mongodb://{self.MONGODB_HOST}:{self.MONGODB_PORT}"
        return self


settings = AsyncWorkerSettings()

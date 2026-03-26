import os
import tempfile
import gettext
import secrets
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # FastAPI
    BASE_URL: str = "localhost"
    API_KEY_NAME: str = "pwd"
    API_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Filesystem
    TEMP_DIR: str = tempfile.gettempdir()
    WORK_DIR: str = os.getcwd()
    DOWNLOAD_DIR: str = ""
    DEBUG_MODE: bool = False

    # Logging
    LOG_FILE_PATH: str = ""
    LOG_LEVEL: str = "DEBUG"

    # MongoDB
    DATABASE_ON: bool = False
    MONGODB_PORT: int = 27017
    MONGODB_HOST: str = "localhost"
    MONGODB_URL: str = ""

    # File exporter
    FILE_EXPORTER_ON: bool = True
    DOWNLOAD_VIDEO_TIMEOUT: int = 600

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # AWS storage
    AWS_STORAGE_ON: bool = False
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET_NAME: str = ""
    AWS_REGION_NAME: str = ""
    AWS_DOMAIN_HOST: Optional[str] = None

    # Inoreader
    INOREADER_APP_ID: Optional[str] = None
    INOREADER_APP_KEY: Optional[str] = None
    INOREADER_EMAIL: Optional[str] = None
    INOREADER_PASSWORD: Optional[str] = None

    # Utils
    HTTP_REQUEST_TIMEOUT: int = 30

    # Telegram Bot callback URL
    TELEGRAM_BOT_CALLBACK_URL: str = "http://telegram-bot:10451"

    @model_validator(mode="after")
    def _resolve_derived(self) -> "ApiSettings":
        if not self.DOWNLOAD_DIR:
            self.DOWNLOAD_DIR = os.path.join(self.WORK_DIR, "download")
        if not self.LOG_FILE_PATH:
            self.LOG_FILE_PATH = self.TEMP_DIR
        if not self.MONGODB_URL:
            self.MONGODB_URL = f"mongodb://{self.MONGODB_HOST}:{self.MONGODB_PORT}"
        if not (self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY and self.AWS_S3_BUCKET_NAME):
            self.AWS_STORAGE_ON = False
        return self


settings = ApiSettings()

# --- Non-settings module-level objects ---

# Locale / i18n
localedir = os.path.join(os.path.dirname(__file__), "locale")
translation = gettext.translation("messages", localedir=localedir, fallback=True)
_ = translation.gettext

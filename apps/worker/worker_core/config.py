import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Conf directory
    CONF_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conf")

    # File export
    DOWNLOAD_DIR: str = "/tmp"
    COOKIE_FILE_PATH: str = ""
    PROXY_MODE: bool = False
    PROXY_URL: str = ""
    YOUTUBE_COOKIE: bool = False
    BILIBILI_COOKIE: bool = False
    OPENAI_API_KEY: str = ""

    @model_validator(mode="after")
    def _resolve_derived(self) -> "WorkerSettings":
        if not self.COOKIE_FILE_PATH:
            self.COOKIE_FILE_PATH = os.path.join(self.CONF_DIR, "cookies.txt")
        return self


settings = WorkerSettings()

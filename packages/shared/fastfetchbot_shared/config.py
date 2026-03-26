import os
import tempfile

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Filesystem
    TEMP_DIR: str = tempfile.gettempdir()
    WORK_DIR: str = os.getcwd()
    DOWNLOAD_DIR: str = ""
    DEBUG_MODE: bool = False

    # Logging
    LOG_FILE_PATH: str = ""
    LOG_LEVEL: str = "DEBUG"

    # Utils
    HTTP_REQUEST_TIMEOUT: int = 30

    # XHS (Xiaohongshu) shared configuration
    SIGN_SERVER_URL: str = "http://localhost:8989"
    XHS_COOKIE_PATH: str = ""

    @model_validator(mode="after")
    def _resolve_derived(self) -> "SharedSettings":
        if not self.DOWNLOAD_DIR:
            self.DOWNLOAD_DIR = os.path.join(self.WORK_DIR, "download")
        if not self.LOG_FILE_PATH:
            self.LOG_FILE_PATH = self.TEMP_DIR
        return self


settings = SharedSettings()

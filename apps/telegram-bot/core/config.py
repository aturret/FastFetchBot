import os
import secrets
from typing import Optional, Union

from jinja2 import Environment, FileSystemLoader
from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramBotSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # API Server connection
    API_SERVER_URL: str = "http://localhost:10450"
    API_KEY_NAME: str = "pwd"
    API_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Bot's own BASE_URL
    BASE_URL: str = "localhost"

    # Telegram bot
    TELEGRAM_BOT_ON: bool = True
    TELEGRAM_BOT_MODE: str = "polling"
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_BOT_SECRET_TOKEN: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32)
    )

    # Channel IDs (raw comma-separated string, parsed after instantiation)
    TELEGRAM_CHANNEL_ID: str = ""
    TELEGRAM_CHANNEL_ADMIN_LIST: str = ""
    TELEBOT_DEBUG_CHANNEL: str = ""

    # Telegram Bot API server
    TELEBOT_API_SERVER_HOST: Optional[str] = None
    TELEBOT_API_SERVER_PORT: Optional[str] = None

    # Telegram Bot server port
    TELEGRAM_BOT_PORT: int = 10451

    # Telegram Bot timeouts (env var names differ from field names)
    TELEBOT_CONNECT_TIMEOUT: int = Field(default=15, validation_alias="TELEGRAM_CONNECT_TIMEOUT")
    TELEBOT_READ_TIMEOUT: int = Field(default=60, validation_alias="TELEGRAM_READ_TIMEOUT")
    TELEBOT_WRITE_TIMEOUT: int = Field(default=60, validation_alias="TELEGRAM_WRITE_TIMEOUT")
    TELEBOT_MAX_RETRY: int = Field(default=5, validation_alias="TELEGRAM_MAX_RETRY")

    # Telegram image limits (fix bug: use separate env var names)
    TELEGRAM_IMAGE_DIMENSION_LIMIT: int = 1600
    TELEGRAM_IMAGE_SIZE_LIMIT: int = 5242880

    # Ban lists (raw comma-separated, parsed after instantiation)
    TELEGRAM_GROUP_MESSAGE_BAN_LIST: str = ""
    TELEGRAM_BOT_MESSAGE_BAN_LIST: str = ""

    # Feature flags
    FILE_EXPORTER_ON: bool = True
    OPENAI_API_KEY: Optional[str] = None
    GENERAL_SCRAPING_ON: bool = False

    # Scrape mode
    SCRAPE_MODE: str = "queue"

    # Redis URLs
    ARQ_REDIS_URL: str = "redis://localhost:6379/2"
    OUTBOX_REDIS_URL: str = "redis://localhost:6379/3"
    OUTBOX_QUEUE_KEY: str = "scrape:outbox"

    # Database
    ITEM_DATABASE_ON: bool = False
    MONGODB_PORT: int = 27017
    MONGODB_HOST: str = "localhost"
    MONGODB_URL: str = ""
    SETTINGS_DATABASE_URL: str = "sqlite+aiosqlite:///data/fastfetchbot.db"

    # Template language
    TEMPLATE_LANGUAGE: str = "zh_CN"

    @model_validator(mode="after")
    def _resolve_derived(self) -> "TelegramBotSettings":
        if not self.MONGODB_URL:
            self.MONGODB_URL = f"mongodb://{self.MONGODB_HOST}:{self.MONGODB_PORT}"
        return self

    @computed_field
    @property
    def TELEGRAM_WEBHOOK_URL(self) -> str:
        return f"https://{self.BASE_URL}/webhook"

    @computed_field
    @property
    def TELEBOT_API_SERVER(self) -> str:
        if self.TELEBOT_API_SERVER_HOST and self.TELEBOT_API_SERVER_PORT:
            return f"http://{self.TELEBOT_API_SERVER_HOST}:{self.TELEBOT_API_SERVER_PORT}/bot"
        return "https://api.telegram.org/bot"

    @computed_field
    @property
    def TELEBOT_API_SERVER_FILE(self) -> str:
        if self.TELEBOT_API_SERVER_HOST and self.TELEBOT_API_SERVER_PORT:
            return f"http://{self.TELEBOT_API_SERVER_HOST}:{self.TELEBOT_API_SERVER_PORT}/file/bot"
        return "https://api.telegram.org/file/bot"

    @computed_field
    @property
    def TELEBOT_LOCAL_FILE_MODE(self) -> bool:
        return self.TELEBOT_API_SERVER != "https://api.telegram.org/bot"


settings = TelegramBotSettings()

# --- Non-settings module-level objects ---

# Jinja2 template configuration
current_directory = os.path.dirname(os.path.abspath(__file__))
templates_directory = os.path.join(current_directory, "templates")
JINJA2_ENV = Environment(
    loader=FileSystemLoader(templates_directory), lstrip_blocks=True, trim_blocks=True
)


# --- Parsed channel/ban list values ---

def _parse_channel_ids(raw: str) -> Optional[list[Union[str, int]]]:
    result: list[Union[str, int]] = []
    for cid in raw.split(","):
        cid = cid.strip()
        if cid.startswith("@"):
            result.append(cid)
        elif cid.startswith("-1"):
            result.append(int(cid))
    return result or None


def _parse_debug_channel(raw: str) -> Optional[Union[str, int]]:
    raw = raw.strip()
    if raw.startswith("@"):
        return raw
    elif raw.startswith("-1"):
        return int(raw)
    return None


def _parse_admin_list(raw: str) -> Optional[list[str]]:
    result = [admin_id.strip() for admin_id in raw.split(",") if admin_id.strip()]
    return result or None


def ban_list_resolver(ban_list_string: str) -> list:
    ban_list = [item.strip() for item in ban_list_string.split(",") if item.strip()]
    expanded = list(ban_list)
    for item in ban_list:
        if item == "social_media":
            expanded.extend([
                "weibo", "twitter", "instagram", "zhihu",
                "douban", "wechat", "xiaohongshu", "reddit",
            ])
        elif item == "video":
            expanded.extend(["youtube", "bilibili"])
    return expanded


TELEGRAM_CHANNEL_ID = _parse_channel_ids(settings.TELEGRAM_CHANNEL_ID)
TELEBOT_DEBUG_CHANNEL = _parse_debug_channel(settings.TELEBOT_DEBUG_CHANNEL)
TELEGRAM_CHANNEL_ADMIN_LIST = _parse_admin_list(settings.TELEGRAM_CHANNEL_ADMIN_LIST)
TELEGRAM_GROUP_MESSAGE_BAN_LIST = ban_list_resolver(settings.TELEGRAM_GROUP_MESSAGE_BAN_LIST)
TELEGRAM_BOT_MESSAGE_BAN_LIST = ban_list_resolver(settings.TELEGRAM_BOT_MESSAGE_BAN_LIST)

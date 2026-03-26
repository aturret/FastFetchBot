import json
import os
import tempfile
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fastfetchbot_shared.utils.cookie import read_json_cookies_to_string
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.pydantic_types import _parse_comma_list, _parse_optional_comma_list


class ScrapersSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Filesystem
    TEMP_DIR: str = tempfile.gettempdir()
    WORK_DIR: str = os.getcwd()
    DOWNLOAD_DIR: str = ""
    DEBUG_MODE: bool = False
    CONF_DIR: str = ""
    TEMPLATE_LANGUAGE: str = "zh_CN"

    # XHS sign server and cookie path (also declared in SharedSettings, read independently)
    SIGN_SERVER_URL: str = "http://localhost:8989"
    XHS_COOKIE_PATH: str = ""

    # X-RapidAPI (shared by Twitter and Instagram scrapers)
    X_RAPIDAPI_KEY: Optional[str] = None

    # Twitter
    TWITTER_EMAIL: Optional[str] = None
    TWITTER_PASSWORD: Optional[str] = None
    TWITTER_USERNAME: Optional[str] = None
    TWITTER_CT0: Optional[str] = None
    TWITTER_AUTH_TOKEN: Optional[str] = None

    # Bluesky
    BLUESKY_USERNAME: Optional[str] = None
    BLUESKY_PASSWORD: Optional[str] = None

    # Weibo (cookie loaded externally)
    WEIBO_COOKIES: Optional[str] = None

    # Xiaohongshu
    XIAOHONGSHU_A1: Optional[str] = None
    XIAOHONGSHU_WEBID: Optional[str] = None
    XIAOHONGSHU_WEBSESSION: Optional[str] = None
    # Stored as comma-separated strings; access parsed lists via computed properties
    XHS_PHONE_LIST: str = ""
    XHS_IP_PROXY_LIST: str = ""
    XHS_ENABLE_IP_PROXY: bool = False
    XHS_SAVE_LOGIN_STATE: bool = True

    # Zhihu
    FXZHIHU_HOST: str = "fxzhihu.com"
    ZHIHU_Z_C0: Optional[str] = None

    # Reddit
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_PASSWORD: Optional[str] = None
    REDDIT_USERNAME: Optional[str] = None

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None

    # General webpage scraping
    GENERAL_SCRAPING_ON: bool = False
    GENERAL_SCRAPING_API: str = "FIRECRAWL"

    # Firecrawl API
    FIRECRAWL_API_URL: str = ""
    FIRECRAWL_API_KEY: str = ""
    FIRECRAWL_WAIT_FOR: str = "3000"
    FIRECRAWL_USE_JSON_EXTRACTION: bool = False

    # Zyte API
    ZYTE_API_KEY: Optional[str] = None

    # Telegraph (comma-separated string; access parsed list via computed property)
    TELEGRAPH_TOKEN_LIST: str = ""

    @model_validator(mode="after")
    def _resolve_derived(self) -> "ScrapersSettings":
        if not self.DOWNLOAD_DIR:
            self.DOWNLOAD_DIR = os.path.join(self.WORK_DIR, "download")
        if not self.CONF_DIR:
            self.CONF_DIR = os.path.join(self.WORK_DIR, "conf")
        return self

    @computed_field
    @property
    def xhs_phone_list(self) -> list[str]:
        """Parse XHS_PHONE_LIST comma-separated string into a list."""
        return _parse_comma_list(self.XHS_PHONE_LIST)

    @computed_field
    @property
    def xhs_ip_proxy_list(self) -> list[str]:
        """Parse XHS_IP_PROXY_LIST comma-separated string into a list."""
        return _parse_comma_list(self.XHS_IP_PROXY_LIST)

    @computed_field
    @property
    def telegraph_token_list(self) -> Optional[list[str]]:
        """Parse TELEGRAPH_TOKEN_LIST comma-separated string into a list, None if empty."""
        return _parse_optional_comma_list(self.TELEGRAPH_TOKEN_LIST)

    @computed_field
    @property
    def TWITTER_COOKIES(self) -> dict[str, Optional[str]]:
        return {"ct0": self.TWITTER_CT0, "auth_token": self.TWITTER_AUTH_TOKEN}

    @computed_field
    @property
    def XIAOHONGSHU_COOKIES(self) -> dict[str, Optional[str]]:
        return {
            "a1": self.XIAOHONGSHU_A1,
            "web_id": self.XIAOHONGSHU_WEBID,
            "web_session": self.XIAOHONGSHU_WEBSESSION,
        }

    @property
    def firecrawl_wait_for_int(self) -> int:
        """Parse FIRECRAWL_WAIT_FOR as int with fallback to 3000."""
        try:
            val = int(self.FIRECRAWL_WAIT_FOR)
            return val if val else 3000
        except (ValueError, TypeError):
            return 3000


settings = ScrapersSettings()

# --- Non-settings module-level objects ---

# Templates & Jinja2
templates_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
JINJA2_ENV = Environment(
    loader=FileSystemLoader(templates_directory), lstrip_blocks=True, trim_blocks=True
)


# --- Cookie file loading (standalone functions) ---

def _load_weibo_cookies(conf_dir: str, env_fallback: Optional[str]) -> Optional[str]:
    weibo_cookies_path = os.path.join(conf_dir, "weibo_cookies.json")
    if os.path.exists(weibo_cookies_path):
        return read_json_cookies_to_string(weibo_cookies_path)
    return env_fallback


def _load_xhs_cookies(
    conf_dir: str,
    xhs_cookie_path: str,
    a1: Optional[str],
    webid: Optional[str],
    websession: Optional[str],
) -> str:
    cookie_path = xhs_cookie_path or os.path.join(conf_dir, "xhs_cookies.txt")
    if os.path.exists(cookie_path):
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except (IOError, OSError) as e:
            logger.error(f"Error reading XHS cookie file: {e}")
            return ""
    cookie_parts = []
    if a1:
        cookie_parts.append(f"a1={a1}")
    if webid:
        cookie_parts.append(f"web_id={webid}")
    if websession:
        cookie_parts.append(f"web_session={websession}")
    return "; ".join(cookie_parts)


def _load_zhihu_cookies(conf_dir: str) -> Optional[dict]:
    zhihu_cookie_path = os.path.join(conf_dir, "zhihu_cookies.json")
    if os.path.exists(zhihu_cookie_path):
        try:
            with open(zhihu_cookie_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Error: zhihu_cookies.json is not in a valid JSON format.")
            return None
        except FileNotFoundError:
            logger.error("Error: zhihu_cookies.json does not exist.")
            return None
    return None


WEIBO_COOKIES = _load_weibo_cookies(settings.CONF_DIR, settings.WEIBO_COOKIES)
XHS_COOKIE_STRING = _load_xhs_cookies(
    settings.CONF_DIR,
    settings.XHS_COOKIE_PATH,
    settings.XIAOHONGSHU_A1,
    settings.XIAOHONGSHU_WEBID,
    settings.XIAOHONGSHU_WEBSESSION,
)
XHS_SIGN_SERVER_URL = settings.SIGN_SERVER_URL
ZHIHU_COOKIES_JSON = _load_zhihu_cookies(settings.CONF_DIR)

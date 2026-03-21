import json
import os
import tempfile

from jinja2 import Environment, FileSystemLoader

from fastfetchbot_shared.utils.cookie import read_json_cookies_to_string
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.parse import get_env_bool

env = os.environ

# Filesystem environment variables
TEMP_DIR = env.get("TEMP_DIR", tempfile.gettempdir())
WORK_DIR = env.get("WORK_DIR", os.getcwd())
DOWNLOAD_DIR = env.get("DOWNLOAD_DIR", os.path.join(WORK_DIR, "download"))
DEBUG_MODE = get_env_bool(env, "DEBUG_MODE", False)

# Cookie/config file directory — defaults to <WORK_DIR>/conf but can be overridden
CONF_DIR = env.get("CONF_DIR", os.path.join(WORK_DIR, "conf"))

# Templates & Jinja2
templates_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
JINJA2_ENV = Environment(
    loader=FileSystemLoader(templates_directory), lstrip_blocks=True, trim_blocks=True
)
TEMPLATE_LANGUAGE = env.get("TEMPLATE_LANGUAGE", "zh_CN")

# X-RapidAPI (shared by Twitter and Instagram scrapers)
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
weibo_cookies_path = os.path.join(CONF_DIR, "weibo_cookies.json")
if os.path.exists(weibo_cookies_path):
    WEIBO_COOKIES = read_json_cookies_to_string(weibo_cookies_path)
else:
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

# XHS sign server and cookie file
from fastfetchbot_shared.config import SIGN_SERVER_URL as XHS_SIGN_SERVER_URL
from fastfetchbot_shared.config import XHS_COOKIE_PATH as _XHS_COOKIE_PATH

xhs_cookie_path = _XHS_COOKIE_PATH or os.path.join(CONF_DIR, "xhs_cookies.txt")

XHS_COOKIE_STRING = ""
if os.path.exists(xhs_cookie_path):
    try:
        with open(xhs_cookie_path, "r", encoding="utf-8") as f:
            XHS_COOKIE_STRING = f.read().strip()
    except (IOError, OSError) as e:
        logger.error(f"Error reading XHS cookie file: {e}")
        XHS_COOKIE_STRING = ""
else:
    cookie_parts = []
    if XIAOHONGSHU_A1:
        cookie_parts.append(f"a1={XIAOHONGSHU_A1}")
    if XIAOHONGSHU_WEBID:
        cookie_parts.append(f"web_id={XIAOHONGSHU_WEBID}")
    if XIAOHONGSHU_WEBSESSION:
        cookie_parts.append(f"web_session={XIAOHONGSHU_WEBSESSION}")
    XHS_COOKIE_STRING = "; ".join(cookie_parts)

# Zhihu
FXZHIHU_HOST = env.get("FXZHIHU_HOST", "fxzhihu.com")
ZHIHU_Z_C0 = env.get("ZHIHU_Z_C0", None)

zhihu_cookie_path = os.path.join(CONF_DIR, "zhihu_cookies.json")
if os.path.exists(zhihu_cookie_path):
    try:
        with open(zhihu_cookie_path, "r") as f:
            ZHIHU_COOKIES_JSON = json.load(f)
    except json.JSONDecodeError:
        logger.error("Error: zhihu_cookies.json is not in a valid JSON format.")
        ZHIHU_COOKIES_JSON = None
    except FileNotFoundError:
        logger.error("Error: zhihu_cookies.json does not exist.")
        ZHIHU_COOKIES_JSON = None
else:
    ZHIHU_COOKIES_JSON = None

# Reddit
REDDIT_CLIENT_ID = env.get("REDDIT_CLIENT_ID", None)
REDDIT_CLIENT_SECRET = env.get("REDDIT_CLIENT_SECRET", None)
REDDIT_PASSWORD = env.get("REDDIT_PASSWORD", None)
REDDIT_USERNAME = env.get("REDDIT_USERNAME", None)

# Open AI API
OPENAI_API_KEY = env.get("OPENAI_API_KEY", None)

# General webpage scraping
GENERAL_SCRAPING_ON = get_env_bool(env, "GENERAL_SCRAPING_ON", False)
GENERAL_SCRAPING_API = env.get("GENERAL_SCRAPING_API", "FIRECRAWL")

# Firecrawl API
FIRECRAWL_API_URL = env.get("FIRECRAWL_API_URL", "")
FIRECRAWL_API_KEY = env.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_WAIT_FOR = int(env.get("FIRECRAWL_WAIT_FOR", 3000))
FIRECRAWL_USE_JSON_EXTRACTION = get_env_bool(env, "FIRECRAWL_USE_JSON_EXTRACTION", False)

# Zyte API
ZYTE_API_KEY = env.get("ZYTE_API_KEY", None)

# Telegraph
telegraph_token_list = env.get("TELEGRAPH_TOKEN_LIST", "")
TELEGRAPH_TOKEN_LIST = telegraph_token_list.split(",") if telegraph_token_list else None

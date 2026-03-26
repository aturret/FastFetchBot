"""Tests for packages/shared/fastfetchbot_shared/services/scrapers/config.py

Since this module executes at import time, every test patches the environment
and then reloads the module via importlib.reload().
"""

import importlib
import json
import os
import sys
import tempfile
from unittest.mock import patch, mock_open, MagicMock

import pytest


def _reload_config(env_overrides=None, path_exists_side_effect=None,
                   open_side_effect=None, open_read_data=None,
                   read_json_cookies_return=None,
                   xhs_cookie_path_override=None):
    """Reload the config module with patched environment and filesystem.

    Returns the freshly-reloaded module object.
    """
    env = {
        # Clear all platform env vars so defaults kick in
    }
    if env_overrides:
        env.update(env_overrides)

    # XHS_COOKIE_PATH is now an env var read by ScrapersSettings
    if xhs_cookie_path_override is not None:
        env["XHS_COOKIE_PATH"] = xhs_cookie_path_override

    patches = []

    # Patch os.environ
    p_env = patch.dict(os.environ, env, clear=True)
    patches.append(p_env)

    # Patch os.path.exists for cookie file checks
    if path_exists_side_effect is not None:
        p_exists = patch("os.path.exists", side_effect=path_exists_side_effect)
        patches.append(p_exists)

    # Patch builtins.open
    if open_side_effect is not None:
        p_open = patch("builtins.open", side_effect=open_side_effect)
        patches.append(p_open)
    elif open_read_data is not None:
        p_open = patch("builtins.open", mock_open(read_data=open_read_data))
        patches.append(p_open)

    # Patch read_json_cookies_to_string
    if read_json_cookies_return is not None:
        p_cookies = patch(
            "fastfetchbot_shared.utils.cookie.read_json_cookies_to_string",
            return_value=read_json_cookies_return,
        )
        patches.append(p_cookies)

    for p in patches:
        p.start()

    mod_name = "fastfetchbot_shared.services.scrapers.config"
    original_module = sys.modules.get(mod_name)
    try:
        # Remove cached module so reload actually re-executes
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import fastfetchbot_shared.services.scrapers.config as cfg
        return cfg
    finally:
        for p in patches:
            p.stop()
        # Restore the original module to avoid polluting other tests
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        if original_module is not None:
            sys.modules[mod_name] = original_module


# ---------------------------------------------------------------------------
# Default values (no env vars set, no cookie files on disk)
# ---------------------------------------------------------------------------

class TestDefaultValues:
    def test_filesystem_defaults(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.TEMP_DIR == tempfile.gettempdir()
        assert cfg.settings.WORK_DIR == os.getcwd()
        assert cfg.settings.DOWNLOAD_DIR == os.path.join(os.getcwd(), "download")
        assert cfg.settings.DEBUG_MODE is False
        assert cfg.settings.CONF_DIR == os.path.join(os.getcwd(), "conf")

    def test_template_defaults(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.TEMPLATE_LANGUAGE == "zh_CN"
        assert cfg.JINJA2_ENV is not None

    def test_platform_defaults_are_none(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.X_RAPIDAPI_KEY is None
        assert cfg.settings.TWITTER_EMAIL is None
        assert cfg.settings.TWITTER_PASSWORD is None
        assert cfg.settings.TWITTER_USERNAME is None
        assert cfg.settings.TWITTER_CT0 is None
        assert cfg.settings.TWITTER_AUTH_TOKEN is None
        assert cfg.settings.TWITTER_COOKIES == {"ct0": None, "auth_token": None}
        assert cfg.settings.BLUESKY_USERNAME is None
        assert cfg.settings.BLUESKY_PASSWORD is None
        assert cfg.settings.XIAOHONGSHU_A1 is None
        assert cfg.settings.XIAOHONGSHU_WEBID is None
        assert cfg.settings.XIAOHONGSHU_WEBSESSION is None
        assert cfg.settings.XIAOHONGSHU_COOKIES == {"a1": None, "web_id": None, "web_session": None}
        assert cfg.settings.REDDIT_CLIENT_ID is None
        assert cfg.settings.REDDIT_CLIENT_SECRET is None
        assert cfg.settings.REDDIT_PASSWORD is None
        assert cfg.settings.REDDIT_USERNAME is None
        assert cfg.settings.OPENAI_API_KEY is None
        assert cfg.settings.ZYTE_API_KEY is None
        assert cfg.settings.ZHIHU_Z_C0 is None

    def test_xhs_defaults(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.xhs_phone_list == []
        assert cfg.settings.xhs_ip_proxy_list == []
        assert cfg.settings.XHS_ENABLE_IP_PROXY is False
        assert cfg.settings.XHS_SAVE_LOGIN_STATE is True

    def test_weibo_cookies_default_from_env(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.WEIBO_COOKIES is None

    def test_zhihu_cookies_default(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.ZHIHU_COOKIES_JSON is None
        assert cfg.settings.FXZHIHU_HOST == "fxzhihu.com"

    def test_general_scraping_defaults(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.GENERAL_SCRAPING_ON is False
        assert cfg.settings.GENERAL_SCRAPING_API == "FIRECRAWL"
        assert cfg.settings.FIRECRAWL_API_URL == ""
        assert cfg.settings.FIRECRAWL_API_KEY == ""
        assert cfg.settings.firecrawl_wait_for_int == 3000
        assert cfg.settings.FIRECRAWL_USE_JSON_EXTRACTION is False

    def test_telegraph_default_empty(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.telegraph_token_list is None

    def test_xhs_cookie_string_empty_when_no_file_no_env(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.XHS_COOKIE_STRING == ""


# ---------------------------------------------------------------------------
# Custom env vars set
# ---------------------------------------------------------------------------

class TestCustomEnvVars:
    def test_custom_filesystem_vars(self):
        cfg = _reload_config(
            env_overrides={
                "TEMP_DIR": "/tmp/custom",
                "WORK_DIR": "/work",
                "DOWNLOAD_DIR": "/work/dl",
                "DEBUG_MODE": "true",
                "CONF_DIR": "/etc/myconf",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.TEMP_DIR == "/tmp/custom"
        assert cfg.settings.WORK_DIR == "/work"
        assert cfg.settings.DOWNLOAD_DIR == "/work/dl"
        assert cfg.settings.DEBUG_MODE is True
        assert cfg.settings.CONF_DIR == "/etc/myconf"

    def test_custom_twitter_vars(self):
        cfg = _reload_config(
            env_overrides={
                "TWITTER_EMAIL": "test@example.com",
                "TWITTER_PASSWORD": "pass123",
                "TWITTER_USERNAME": "tuser",
                "TWITTER_CT0": "ct0val",
                "TWITTER_AUTH_TOKEN": "authval",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.TWITTER_EMAIL == "test@example.com"
        assert cfg.settings.TWITTER_PASSWORD == "pass123"
        assert cfg.settings.TWITTER_USERNAME == "tuser"
        assert cfg.settings.TWITTER_CT0 == "ct0val"
        assert cfg.settings.TWITTER_AUTH_TOKEN == "authval"
        assert cfg.settings.TWITTER_COOKIES == {"ct0": "ct0val", "auth_token": "authval"}

    def test_custom_bluesky_vars(self):
        cfg = _reload_config(
            env_overrides={
                "BLUESKY_USERNAME": "buser",
                "BLUESKY_PASSWORD": "bpass",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.BLUESKY_USERNAME == "buser"
        assert cfg.settings.BLUESKY_PASSWORD == "bpass"

    def test_custom_xhs_phone_and_proxy(self):
        cfg = _reload_config(
            env_overrides={
                "XHS_PHONE_LIST": "111,222,333",
                "XHS_IP_PROXY_LIST": "p1,p2",
                "XHS_ENABLE_IP_PROXY": "true",
                "XHS_SAVE_LOGIN_STATE": "false",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.xhs_phone_list == ["111", "222", "333"]
        assert cfg.settings.xhs_ip_proxy_list == ["p1", "p2"]
        assert cfg.settings.XHS_ENABLE_IP_PROXY is True
        assert cfg.settings.XHS_SAVE_LOGIN_STATE is False

    def test_custom_template_language(self):
        cfg = _reload_config(
            env_overrides={"TEMPLATE_LANGUAGE": "en_US"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.TEMPLATE_LANGUAGE == "en_US"

    def test_custom_reddit_vars(self):
        cfg = _reload_config(
            env_overrides={
                "REDDIT_CLIENT_ID": "rcid",
                "REDDIT_CLIENT_SECRET": "rsec",
                "REDDIT_PASSWORD": "rpass",
                "REDDIT_USERNAME": "ruser",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.REDDIT_CLIENT_ID == "rcid"
        assert cfg.settings.REDDIT_CLIENT_SECRET == "rsec"
        assert cfg.settings.REDDIT_PASSWORD == "rpass"
        assert cfg.settings.REDDIT_USERNAME == "ruser"

    def test_custom_general_scraping_vars(self):
        cfg = _reload_config(
            env_overrides={
                "GENERAL_SCRAPING_ON": "true",
                "GENERAL_SCRAPING_API": "ZYTE",
                "FIRECRAWL_API_URL": "https://fc.example.com",
                "FIRECRAWL_API_KEY": "fc-key",
                "FIRECRAWL_WAIT_FOR": "5000",
                "FIRECRAWL_USE_JSON_EXTRACTION": "true",
                "ZYTE_API_KEY": "zyte-key",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.GENERAL_SCRAPING_ON is True
        assert cfg.settings.GENERAL_SCRAPING_API == "ZYTE"
        assert cfg.settings.FIRECRAWL_API_URL == "https://fc.example.com"
        assert cfg.settings.FIRECRAWL_API_KEY == "fc-key"
        assert cfg.settings.firecrawl_wait_for_int == 5000
        assert cfg.settings.FIRECRAWL_USE_JSON_EXTRACTION is True
        assert cfg.settings.ZYTE_API_KEY == "zyte-key"

    def test_custom_openai_key(self):
        cfg = _reload_config(
            env_overrides={"OPENAI_API_KEY": "sk-test"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.OPENAI_API_KEY == "sk-test"

    def test_custom_x_rapidapi_key(self):
        cfg = _reload_config(
            env_overrides={"X_RAPIDAPI_KEY": "rapid-key"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.X_RAPIDAPI_KEY == "rapid-key"

    def test_custom_weibo_cookies_from_env(self):
        cfg = _reload_config(
            env_overrides={"WEIBO_COOKIES": "some_cookie_string"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.WEIBO_COOKIES == "some_cookie_string"

    def test_custom_zhihu_vars(self):
        cfg = _reload_config(
            env_overrides={
                "FXZHIHU_HOST": "custom.zhihu.com",
                "ZHIHU_Z_C0": "z_c0_val",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.FXZHIHU_HOST == "custom.zhihu.com"
        assert cfg.settings.ZHIHU_Z_C0 == "z_c0_val"


# ---------------------------------------------------------------------------
# Weibo cookies from file vs env
# ---------------------------------------------------------------------------

class TestWeiboCookies:
    def test_weibo_cookies_from_file(self):
        def exists_side_effect(path):
            if "weibo_cookies.json" in path:
                return True
            return False

        cfg = _reload_config(
            path_exists_side_effect=exists_side_effect,
            read_json_cookies_return="name1=val1; name2=val2",
        )
        assert cfg.WEIBO_COOKIES == "name1=val1; name2=val2"

    def test_weibo_cookies_fallback_to_env(self):
        cfg = _reload_config(
            env_overrides={"WEIBO_COOKIES": "env_weibo_cookies"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.WEIBO_COOKIES == "env_weibo_cookies"


# ---------------------------------------------------------------------------
# XHS cookie string: from file, from env parts, file IOError
# ---------------------------------------------------------------------------

class TestXhsCookieString:
    def test_xhs_cookie_from_file(self):
        xhs_path = "/fake/xhs_cookies.txt"

        def exists_side_effect(path):
            if path == xhs_path:
                return True
            return False

        cfg = _reload_config(
            path_exists_side_effect=exists_side_effect,
            open_read_data="  a1=x; web_id=y; web_session=z  \n",
            xhs_cookie_path_override=xhs_path,
        )
        assert cfg.XHS_COOKIE_STRING == "a1=x; web_id=y; web_session=z"

    def test_xhs_cookie_from_env_parts(self):
        cfg = _reload_config(
            env_overrides={
                "XIAOHONGSHU_A1": "a1val",
                "XIAOHONGSHU_WEBID": "webidval",
                "XIAOHONGSHU_WEBSESSION": "sessionval",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.XHS_COOKIE_STRING == "a1=a1val; web_id=webidval; web_session=sessionval"

    def test_xhs_cookie_from_env_partial(self):
        """Only some XHS env vars set."""
        cfg = _reload_config(
            env_overrides={
                "XIAOHONGSHU_A1": "a1only",
            },
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.XHS_COOKIE_STRING == "a1=a1only"

    def test_xhs_cookie_file_ioerror(self):
        xhs_path = "/fake/xhs_cookies.txt"

        def exists_side_effect(path):
            if path == xhs_path:
                return True
            return False

        cfg = _reload_config(
            path_exists_side_effect=exists_side_effect,
            open_side_effect=IOError("disk error"),
            xhs_cookie_path_override=xhs_path,
        )
        assert cfg.XHS_COOKIE_STRING == ""

    def test_xhs_cookie_default_path_when_no_override(self):
        """When XHS_COOKIE_PATH is empty, _load_xhs_cookies uses CONF_DIR/xhs_cookies.txt."""
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
            xhs_cookie_path_override="",
        )
        # The settings field stores the raw env value (empty string)
        assert cfg.settings.XHS_COOKIE_PATH == ""


# ---------------------------------------------------------------------------
# Zhihu cookies: valid JSON, invalid JSON, missing file, no file
# ---------------------------------------------------------------------------

class TestZhihuCookies:
    def test_zhihu_cookies_valid_json(self):
        zhihu_data = [{"name": "z_c0", "value": "abc"}]

        def exists_side_effect(path):
            if "zhihu_cookies.json" in path:
                return True
            return False

        cfg = _reload_config(
            path_exists_side_effect=exists_side_effect,
            open_read_data=json.dumps(zhihu_data),
        )
        assert cfg.ZHIHU_COOKIES_JSON == zhihu_data

    def test_zhihu_cookies_invalid_json(self):
        def exists_side_effect(path):
            if "zhihu_cookies.json" in path:
                return True
            return False

        cfg = _reload_config(
            path_exists_side_effect=exists_side_effect,
            open_read_data="not valid json {{{",
        )
        assert cfg.ZHIHU_COOKIES_JSON is None

    def test_zhihu_cookies_file_not_found_exception(self):
        """File exists per os.path.exists but open raises FileNotFoundError (race)."""
        def exists_side_effect(path):
            if "zhihu_cookies.json" in path:
                return True
            return False

        cfg = _reload_config(
            path_exists_side_effect=exists_side_effect,
            open_side_effect=FileNotFoundError("gone"),
        )
        assert cfg.ZHIHU_COOKIES_JSON is None

    def test_zhihu_cookies_no_file(self):
        cfg = _reload_config(
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.ZHIHU_COOKIES_JSON is None


# ---------------------------------------------------------------------------
# FIRECRAWL_WAIT_FOR (stored as str, parsed via firecrawl_wait_for_int)
# ---------------------------------------------------------------------------

class TestFirecrawlWaitFor:
    def test_firecrawl_wait_for_invalid_fallback(self):
        """Non-numeric string should fall back to 3000 via firecrawl_wait_for_int."""
        cfg = _reload_config(
            env_overrides={"FIRECRAWL_WAIT_FOR": "not_a_number"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.firecrawl_wait_for_int == 3000

    def test_firecrawl_wait_for_valid(self):
        cfg = _reload_config(
            env_overrides={"FIRECRAWL_WAIT_FOR": "7000"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.firecrawl_wait_for_int == 7000

    def test_firecrawl_wait_for_empty_string(self):
        """Empty string should fall back to 3000 via firecrawl_wait_for_int."""
        cfg = _reload_config(
            env_overrides={"FIRECRAWL_WAIT_FOR": ""},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.firecrawl_wait_for_int == 3000


# ---------------------------------------------------------------------------
# TELEGRAPH_TOKEN_LIST (stored as str, parsed via telegraph_token_list)
# ---------------------------------------------------------------------------

class TestTelegraphTokenList:
    def test_telegraph_empty_string(self):
        cfg = _reload_config(
            env_overrides={"TELEGRAPH_TOKEN_LIST": ""},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.telegraph_token_list is None

    def test_telegraph_comma_separated(self):
        cfg = _reload_config(
            env_overrides={"TELEGRAPH_TOKEN_LIST": "tok1,tok2,tok3"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.telegraph_token_list == ["tok1", "tok2", "tok3"]

    def test_telegraph_single_token(self):
        cfg = _reload_config(
            env_overrides={"TELEGRAPH_TOKEN_LIST": "single_tok"},
            path_exists_side_effect=lambda p: False,
        )
        assert cfg.settings.telegraph_token_list == ["single_tok"]

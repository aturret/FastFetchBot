import json
import os
from typing import Optional

from fastfetchbot_shared.utils.logger import logger


def read_json_cookies_to_string(file_path: str) -> Optional[str]:
    """Read a JSON cookie file and convert it to a cookie header string.

    Expects the standard browser extension format (e.g. "Get cookies.txt LOCALLY"):
        [{"name": "cookie_name", "value": "cookie_value"}, ...]

    Returns a semicolon-separated cookie string like:
        "cookie_name1=cookie_value1; cookie_name2=cookie_value2"

    Returns None if the file doesn't exist, is invalid JSON, or contains no cookies.
    """
    if not os.path.exists(file_path):
        logger.warning(f"Cookie file not found: {file_path}")
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        logger.error(f"Error reading cookie file {file_path}: {e}")
        return None

    if not isinstance(cookies, list) or not cookies:
        logger.warning(f"Cookie file {file_path} does not contain a valid cookie list")
        return None

    return "; ".join(
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if "name" in cookie and "value" in cookie
    )

"""Bilibili video ID parsing. Standard library only, so the worker can import it."""

import re
from urllib.parse import parse_qs, urlparse

VIDEO_PATH_RE = re.compile(r"^/video/(BV[0-9A-Za-z]{10}|av\d+)/?$", re.I)


class InvalidBilibiliVideoUrl(ValueError):
    """The URL is not a canonical Bilibili video URL."""


def parse_page(query: str) -> int | None:
    values = parse_qs(query).get("p")
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None


def extract_video_id(url: str) -> dict:
    """Return the view-API params for a canonical video URL plus the page number.

    Example: {"bvid": "BV1xx411c7mD", "p": 1} or {"aid": "170001", "p": 2}.
    """
    parsed = urlparse(url)
    match = VIDEO_PATH_RE.match(parsed.path)
    if not match:
        raise InvalidBilibiliVideoUrl(f"无法从链接中识别 B 站视频 ID：{url}")
    video_id = match.group(1)
    page = parse_page(parsed.query) or 1
    if video_id[:2].lower() == "av":
        return {"aid": video_id[2:], "p": page}
    return {"bvid": video_id, "p": page}


# Bilibili API `code` values. Fatal: the video can't be fetched by any means.
FATAL_CODES = {
    -404: "视频不存在或已删除",
    62002: "稿件不可见",
    62004: "稿件审核中",
    62012: "仅 UP 主自己可见",
}
# Retryable: risk control or permissions; another route may still work.
RETRYABLE_CODES = {
    -352: "B 站风控拦截",
    -403: "访问权限不足",
    -412: "B 站风控拦截",
}

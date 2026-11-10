"""Bilibili URL helpers shared by the API scrapers and the Celery worker.

Keep this module free of scraper dependencies: the worker installs only the
base `fastfetchbot-shared` package.
"""

import re
from urllib.parse import parse_qs, urlparse

import httpx

DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)
SHORT_LINK_HOSTS = ("b23.tv", "bili2233.cn")
SHORT_LINK_TIMEOUT = 15.0

VIDEO_PATH_RE = re.compile(r"^/video/(BV[0-9A-Za-z]{10}|av\d+)/?$", re.I)
# t.bilibili.com/{id}, www/m.bilibili.com/opus/{id}, m.bilibili.com/dynamic/{id}
DYNAMIC_URL_RE = re.compile(
    r"^(?:t\.bilibili\.com/|(?:www\.|m\.)?bilibili\.com/(?:opus|dynamic)/)(\d{18,19})/?$"
)


def host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def is_short_link(url: str) -> bool:
    host = (urlparse(url if "://" in url else "https://" + url).hostname or "").lower()
    return any(host_matches(host, h) for h in SHORT_LINK_HOSTS)


async def expand_short_link(url: str) -> str:
    """Follow a b23.tv / bili2233.cn redirect chain. Raises httpx.HTTPError."""
    if "://" not in url:
        url = "https://" + url
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=SHORT_LINK_TIMEOUT,
        headers={"User-Agent": DESKTOP_USER_AGENT},
    ) as client:
        resp = await client.get(url)
    return str(resp.url)


def extract_dynamic_id(url: str) -> str | None:
    """Return the dynamic ID from a dynamic/opus URL, or None for other URLs."""
    parsed = urlparse(url if "://" in url else "https://" + url)
    match = DYNAMIC_URL_RE.match(f"{(parsed.hostname or '').lower()}{parsed.path}")
    return match.group(1) if match else None


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

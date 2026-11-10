"""Bilibili official web API: fetch video metadata without yt-dlp."""

import httpx

from fastfetchbot_shared.exceptions import ScraperError
from fastfetchbot_shared.utils.parse import second_to_time, unix_timestamp_to_utc
from fastfetchbot_shared.utils.bilibili import FATAL_CODES, RETRYABLE_CODES
from .url import DESKTOP_USER_AGENT, extract_video_id

VIEW_API = "https://api.bilibili.com/x/web-interface/view"
API_TIMEOUT = 15.0
API_HEADERS = {
    "User-Agent": DESKTOP_USER_AGENT,
    "Referer": "https://www.bilibili.com/",
}


class BilibiliApiUnavailable(ScraperError):
    """The official API failed in a way the yt-dlp fallback may still recover from."""


async def fetch_bilibili_video_meta(url: str) -> dict:
    """Fetch metadata for a canonical video URL.

    Returns the same shape as VideoDownloader._bilibili_info_parse.
    Raises ScraperError for unrecoverable cases, BilibiliApiUnavailable otherwise.
    """
    ids = extract_video_id(url)
    page = ids.pop("p")
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT, headers=API_HEADERS) as client:
            resp = await client.get(VIEW_API, params=ids)
    except httpx.HTTPError as e:
        raise BilibiliApiUnavailable(f"B 站接口请求失败：{type(e).__name__}") from e

    if resp.status_code == 412:
        raise BilibiliApiUnavailable("B 站风控拦截（HTTP 412）")
    if resp.status_code != 200:
        raise BilibiliApiUnavailable(f"B 站接口返回 HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as e:
        raise BilibiliApiUnavailable("B 站接口返回的不是 JSON") from e
    if not isinstance(payload, dict):
        raise BilibiliApiUnavailable("B 站接口数据结构异常：响应不是 JSON 对象")

    code = payload.get("code")
    if code in FATAL_CODES:
        raise ScraperError(f"B 站视频获取失败：{FATAL_CODES[code]}")
    if code != 0:
        reason = RETRYABLE_CODES.get(code) or payload.get("message") or "未知错误"
        raise BilibiliApiUnavailable(f"B 站接口错误 {code}：{reason}")

    try:
        return _parse_view(payload["data"], page)
    except (KeyError, TypeError, ValueError) as e:
        raise BilibiliApiUnavailable(f"B 站接口数据结构异常：{e!r}") from e


def _parse_view(data: dict, page: int) -> dict:
    owner = data.get("owner") or {}
    stat = data.get("stat") or {}
    pages = data.get("pages") or []
    page_info = next((p for p in pages if p.get("page") == page), None)
    duration = (page_info or {}).get("duration") or data["duration"]
    description = (data.get("desc") or "").strip()
    if description == "-":
        description = ""
    pubdate = data.get("pubdate") or None
    return {
        "id": data["bvid"],
        "title": data["title"],
        "author": owner.get("name", ""),
        "author_url": f"https://space.bilibili.com/{owner.get('mid', '')}",
        "author_avatar": data.get("pic", ""),
        "ext": "mp4",
        "description": description,
        "playback_data": (
            f"视频播放量：{stat.get('view', 0)} "
            f"弹幕数：{stat.get('danmaku', 0)} "
            f"点赞数：{stat.get('like', 0)}"
        ),
        "upload_date": unix_timestamp_to_utc(pubdate) if pubdate else None,
        "timestamp": pubdate,
        "duration": second_to_time(round(duration)),
    }

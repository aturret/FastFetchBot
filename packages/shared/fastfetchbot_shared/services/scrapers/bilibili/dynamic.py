"""Bilibili dynamics (动态) and opus (图文) via the polymer web-dynamic detail API.

The fetch/parse approach follows ParseHub (third-party, ideas only): request a
fresh anonymous buvid pair each time to avoid -352 risk control, then read
`data.item.modules`. Every major type maps to title / text / images; forwards
also carry the original dynamic.
"""

import re
from typing import Any

import httpx

from fastfetchbot_shared.exceptions import ScraperError
from fastfetchbot_shared.utils.bilibili import DESKTOP_USER_AGENT

SPI_API = "https://api.bilibili.com/x/frontend/finger/spi"
DETAIL_API = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"
API_TIMEOUT = 15.0

DYNAMIC_ERRORS = {
    -352: "B 站风控拦截",
    4101152: "动态不可见",
}

_HASHTAG_RE = re.compile(r"#([^#\n]+)#")


def clean_bilibili_hashtags(text: str | None) -> str:
    """`#话题#` -> `#话题`, with exactly one space separating it from neighbouring text."""
    if not text:
        return ""
    result = ""
    pos = 0
    for m in _HASHTAG_RE.finditer(text):
        result += text[pos:m.start()]
        if result and not result[-1].isspace():
            result += " "
        result += f"#{m.group(1).strip()}"
        pos = m.end()
        if pos < len(text) and not text[pos].isspace():
            result += " "
    return (result + text[pos:]).strip()


async def fetch_dynamic_item(dynamic_id: str) -> dict:
    """Return `data.item` from the detail API. Raises ScraperError with a user-facing reason."""
    headers = {"User-Agent": DESKTOP_USER_AGENT, "Referer": f"https://t.bilibili.com/{dynamic_id}"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=API_TIMEOUT) as client:
            await _set_guest_cookies(client)
            resp = await client.get(
                DETAIL_API,
                params={"id": dynamic_id, "timezone_offset": "-480", "features": "itemOpusStyle"},
            )
    except httpx.HTTPError as e:
        raise ScraperError(f"B 站动态获取失败：{type(e).__name__}") from e

    if resp.status_code == 412:
        raise ScraperError("B 站动态获取失败：B 站风控拦截（HTTP 412）")
    if resp.status_code != 200:
        raise ScraperError(f"B 站动态获取失败：HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as e:
        raise ScraperError("B 站动态获取失败：返回的不是 JSON") from e

    item = (payload.get("data") or {}).get("item")
    if payload.get("code") != 0 or not isinstance(item, dict):
        code = payload.get("code")
        reason = DYNAMIC_ERRORS.get(code) or payload.get("message") or "未知错误"
        raise ScraperError(f"B 站动态获取失败：{reason}（{code}）")
    return item


async def _set_guest_cookies(client: httpx.AsyncClient) -> None:
    try:
        data = (await client.get(SPI_API)).json()["data"]
        client.cookies.set("buvid3", data["b_3"], domain=".bilibili.com")
        client.cookies.set("buvid4", data["b_4"], domain=".bilibili.com")
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        # Not fatal: the detail request reports the real problem if there is one.
        pass


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_dynamic_item(item: dict) -> dict:
    """Normalize one dynamic item.

    Returns {id, type, author, author_mid, timestamp, title, text, link, images,
    stats, orig}; `images` items are {url, width, height, live_url}; `orig` is
    the same shape for forwards, else None.
    """
    modules = item.get("modules") or {}
    author = modules.get("module_author") or {}
    module_dynamic = modules.get("module_dynamic") or {}
    stat = modules.get("module_stat") or {}

    parsed = _parse_body(module_dynamic)
    orig = item.get("orig")
    return {
        "id": str(item.get("id_str") or ""),
        "type": item.get("type") or "",
        "author": author.get("name") or "",
        "author_mid": author.get("mid"),
        "timestamp": _to_int(author.get("pub_ts")),
        **parsed,
        "stats": {
            "comment": _count(stat.get("comment")),
            "forward": _count(stat.get("forward")),
            "like": _count(stat.get("like")),
        },
        "orig": parse_dynamic_item(orig) if isinstance(orig, dict) and orig.get("modules") else None,
    }


def _parse_body(module_dynamic: dict) -> dict:
    desc_text = _desc_text(module_dynamic)
    major = module_dynamic.get("major") or {}
    handler = _MAJOR_HANDLERS.get(major.get("type"))
    body = handler(major) if handler else {}
    text = desc_text or body.get("text") or ""
    return {
        "title": body.get("title") or "",
        "text": clean_bilibili_hashtags(text),
        "link": body.get("link"),
        "images": body.get("images") or [],
    }


def _desc_text(module_dynamic: dict) -> str:
    desc = module_dynamic.get("desc") or {}
    return str(desc.get("text") or "").strip()


def _cover(content: dict) -> list[dict]:
    cover = content.get("cover")
    return [_image(cover)] if cover else []


def _image(url: str, width: Any = 0, height: Any = 0, live_url: str | None = None) -> dict:
    return {
        "url": _https(url),
        "width": _to_int(width) or 0,
        "height": _to_int(height) or 0,
        "live_url": _https(live_url) if live_url else None,
    }


def _major_opus(major: dict) -> dict:
    opus = major.get("opus") or {}
    pics = opus.get("pics") or []
    return {
        "title": opus.get("title") or "",
        "text": (opus.get("summary") or {}).get("text") or "",
        "images": [_image(p["url"], p.get("width"), p.get("height"), p.get("live_url")) for p in pics if p.get("url")],
    }


def _major_archive(major: dict) -> dict:
    archive = major.get("archive") or {}
    return {
        "title": archive.get("title") or "",
        "text": archive.get("desc") or "",
        "link": _https(archive.get("jump_url")) or (
            f"https://www.bilibili.com/video/{archive['bvid']}" if archive.get("bvid") else None
        ),
        "images": _cover(archive),
    }


def _simple(key: str, text_fields: tuple[str, ...] = ("desc",)) -> Any:
    def handler(major: dict) -> dict:
        content = major.get(key) or {}
        text = "\n\n".join(str(content[f]) for f in text_fields if content.get(f))
        return {
            "title": content.get("title") or "",
            "text": text,
            "link": _https(content.get("jump_url")),
            "images": _cover(content),
        }

    return handler


def _major_live(major: dict) -> dict:
    live = major.get("live") or {}
    text = " · ".join(str(live[f]) for f in ("desc_first", "desc_second") if live.get(f))
    return {"title": live.get("title") or "", "text": text, "link": _https(live.get("jump_url")), "images": _cover(live)}


def _major_upower_common(major: dict) -> dict:
    content = major.get("upower_common") or {}
    prefix, title = content.get("title_prefix"), content.get("title") or ""
    return {"title": f"{prefix}: {title}" if prefix else title}


_MAJOR_HANDLERS = {
    "MAJOR_TYPE_OPUS": _major_opus,
    "MAJOR_TYPE_ARCHIVE": _major_archive,
    "MAJOR_TYPE_PGC": _simple("pgc", ()),
    "MAJOR_TYPE_MUSIC": _simple("music", ()),
    "MAJOR_TYPE_COMMON": _simple("common"),
    "MAJOR_TYPE_LIVE": _major_live,
    "MAJOR_TYPE_MEDIALIST": _simple("medialist", ("sub_title",)),
    "MAJOR_TYPE_COURSES": _simple("courses", ("sub_title", "desc")),
    "MAJOR_TYPE_UGC_SEASON": _simple("ugc_season"),
    "MAJOR_TYPE_UPOWER_COMMON": _major_upower_common,
}


def _https(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _count(stat: Any) -> int | None:
    return _to_int(stat.get("count")) if isinstance(stat, dict) else None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

"""Guest (no-login) Bilibili download, used when yt-dlp fails.

Flow: anonymous buvid cookies -> view API (cid) -> playurl with fnval=1 (a single
MP4 with audio, no merge needed) -> stream the file, trying CDN mirrors in turn.
Synchronous on purpose: it runs inside the Celery worker next to yt-dlp, and its
output lands in the same DOWNLOAD_DIR the bot reads from.
"""

import os
import re

import httpx
from loguru import logger
from yt_dlp.utils import sanitize_filename

from fastfetchbot_shared.utils.bilibili import (
    FATAL_CODES,
    RETRYABLE_CODES,
    InvalidBilibiliVideoUrl,
    extract_video_id,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"
SPI_API = "https://api.bilibili.com/x/frontend/finger/spi"
VIEW_API = "https://api.bilibili.com/x/web-interface/view"
PLAYURL_API = "https://api.bilibili.com/x/player/playurl"
QN_720P = 64
FNVAL_MP4 = 1
STABLE_CDN_HOST = "upos-sz-upcdnbda2.bilivideo.com"
_UPOS_HOST_RE = re.compile(r"upos-[^/]*?\.(?:bilivideo\.com|mirrorakam\.akamaized\.net)")
API_TIMEOUT = 15.0
DOWNLOAD_TIMEOUT = httpx.Timeout(30.0, read=120.0)
CHUNK_SIZE = 1 << 20


class GuestDownloadError(Exception):
    """Guest download failed; the message is user-facing."""


def guest_download(url: str, download_dir: str, proxy: str | None = None) -> dict:
    """Download a canonical Bilibili video URL without login.

    Returns {"content_info": <yt-dlp-shaped metadata>, "file_path": <local path>}.
    """
    try:
        ids = extract_video_id(url)
    except InvalidBilibiliVideoUrl as e:
        raise GuestDownloadError(str(e)) from e
    page = ids.pop("p")

    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Referer": REFERER},
        proxy=proxy,
        follow_redirects=True,
        timeout=API_TIMEOUT,
    ) as client:
        _set_guest_cookies(client)
        view = _api_get(client, VIEW_API, ids, "视频信息")
        page_info = _select_page(view, page)
        playurl = _api_get(
            client,
            PLAYURL_API,
            {
                "bvid": view["bvid"],
                "cid": page_info["cid"],
                "qn": QN_720P,
                "fnval": FNVAL_MP4,
                "fourk": 1,
            },
            "播放地址",
        )
        durl = (playurl.get("durl") or [None])[0]
        if not durl:
            raise GuestDownloadError("没有可用的游客下载地址")
        logger.info(f"Bilibili guest download: bvid={view['bvid']} quality={playurl.get('quality')}")

        file_name = sanitize_filename(f"{view['title'][:10]}-{view['bvid']}.mp4")
        file_path = os.path.join(download_dir, file_name)
        _download_first_working(client, _candidate_urls(durl), file_path)

    return {"content_info": _content_info(view, page_info), "file_path": file_path}


def _set_guest_cookies(client: httpx.Client) -> None:
    try:
        data = client.get(SPI_API).json()["data"]
        client.cookies.set("buvid3", data["b_3"], domain=".bilibili.com")
        client.cookies.set("buvid4", data["b_4"], domain=".bilibili.com")
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        # Not fatal: the next API call will report the real problem if any.
        logger.warning(f"Bilibili guest cookie request failed: {e!r}")


def _api_get(client: httpx.Client, endpoint: str, params: dict, what: str) -> dict:
    try:
        resp = client.get(endpoint, params=params)
    except httpx.HTTPError as e:
        raise GuestDownloadError(f"获取{what}失败：{type(e).__name__}") from e
    if resp.status_code == 412:
        raise GuestDownloadError("B 站风控拦截（HTTP 412）")
    if resp.status_code != 200:
        raise GuestDownloadError(f"获取{what}失败：HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as e:
        raise GuestDownloadError(f"获取{what}失败：返回的不是 JSON") from e
    if not isinstance(payload, dict):
        raise GuestDownloadError(f"获取{what}失败：数据结构异常")
    code = payload.get("code")
    if code != 0:
        reason = FATAL_CODES.get(code) or RETRYABLE_CODES.get(code) or payload.get("message") or "未知错误"
        raise GuestDownloadError(f"获取{what}失败：{reason}（{code}）")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise GuestDownloadError(f"获取{what}失败：数据结构异常")
    return data


def _select_page(view: dict, page: int) -> dict:
    pages = view.get("pages") or []
    page_info = next((p for p in pages if p.get("page") == page), None) or (pages[0] if pages else None)
    if page_info is None:
        return {"cid": view["cid"], "duration": view.get("duration"), "dimension": view.get("dimension") or {}}
    return page_info


def _candidate_urls(durl: dict) -> list[str]:
    backups = durl.get("backup_url") or []
    candidates = [_UPOS_HOST_RE.sub(STABLE_CDN_HOST, u) for u in backups]
    candidates += backups
    if durl.get("url"):
        candidates.append(durl["url"])
    return list(dict.fromkeys(candidates))  # dedupe, keep order


def _download_first_working(client: httpx.Client, urls: list[str], file_path: str) -> None:
    part_path = file_path + ".part"
    last_error = "没有候选地址"
    for candidate in urls:
        try:
            with client.stream("GET", candidate, timeout=DOWNLOAD_TIMEOUT) as resp:
                if resp.status_code not in (200, 206):
                    last_error = f"HTTP {resp.status_code}"
                    logger.warning(f"Bilibili guest CDN rejected ({last_error}): {httpx.URL(candidate).host}")
                    continue
                with open(part_path, "wb") as f:
                    for chunk in resp.iter_bytes(CHUNK_SIZE):
                        f.write(chunk)
            os.replace(part_path, file_path)
            return
        except httpx.HTTPError as e:
            last_error = type(e).__name__
            logger.warning(f"Bilibili guest CDN error ({last_error}): {httpx.URL(candidate).host}")
        finally:
            if os.path.exists(part_path):
                os.remove(part_path)
    raise GuestDownloadError(f"所有下载节点都失败（{last_error}）")


def _content_info(view: dict, page_info: dict) -> dict:
    owner = view.get("owner") or {}
    stat = view.get("stat") or {}
    dimension = page_info.get("dimension") or view.get("dimension") or {}
    width, height = dimension.get("width") or 0, dimension.get("height") or 0
    if dimension.get("rotate"):
        width, height = height, width
    description = (view.get("desc") or "").strip()
    return {
        "id": view["bvid"],
        "title": view["title"],
        "uploader": owner.get("name", ""),
        "uploader_id": owner.get("mid"),
        "uploader_url": None,
        "channel_url": None,
        "description": "" if description == "-" else description,
        "view_count": stat.get("view"),
        # The bot's template labels this field "弹幕数".
        "comment_count": stat.get("danmaku"),
        "like_count": stat.get("like"),
        "thumbnail": view.get("pic"),
        "upload_date": None,
        "timestamp": view.get("pubdate"),
        "duration": page_info.get("duration") or view.get("duration") or 0,
        "ext": "mp4",
        "formats": [{"aspect_ratio": round(width / height, 3)}] if width and height else [],
    }

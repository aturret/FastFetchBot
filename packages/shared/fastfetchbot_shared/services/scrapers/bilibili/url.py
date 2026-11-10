"""Bilibili URL normalization: expand short links, strip tracking, reject non-video pages."""

from urllib.parse import urlencode, urlparse

import httpx

from fastfetchbot_shared.exceptions import ScraperError
from fastfetchbot_shared.utils import bilibili as bili_id

DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)
SHORT_LINK_HOSTS = ("b23.tv", "bili2233.cn")
REDIRECT_TIMEOUT = 15.0


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


async def _expand_short_link(url: str) -> str:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=REDIRECT_TIMEOUT,
            headers={"User-Agent": DESKTOP_USER_AGENT},
        ) as client:
            resp = await client.get(url)
    except httpx.HTTPError as e:
        raise ScraperError(f"B 站短链展开失败：{type(e).__name__}") from e
    return str(resp.url)


async def resolve_bilibili_url(url: str) -> str:
    """Return a canonical `https://www.bilibili.com/video/{id}[?p=N]` URL.

    Raises ScraperError with a user-facing reason for unsupported pages
    (bangumi, live, mall) or links that don't land on a video.
    """
    if "://" not in url:
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower()
    if any(_host_matches(host, h) for h in SHORT_LINK_HOSTS):
        url = await _expand_short_link(url)

    # Re-parse after the redirect: the final host decides what this link is.
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path

    if _host_matches(host, "live.bilibili.com"):
        raise ScraperError("暂不支持 B 站直播")
    if _host_matches(host, "mall.bilibili.com"):
        raise ScraperError("暂不支持 B 站商品")
    if not _host_matches(host, "bilibili.com"):
        raise ScraperError(f"不是 B 站视频链接：{host or url}")
    if path.startswith("/bangumi/"):
        raise ScraperError("暂不支持 B 站番剧/影视")

    match = bili_id.VIDEO_PATH_RE.match(path)
    if not match:
        raise ScraperError("不是 B 站视频链接（短链可能已失效）")

    video_id = match.group(1)
    if video_id[:2].lower() == "av":
        video_id = "av" + video_id[2:]
    canonical = f"https://www.bilibili.com/video/{video_id}"

    page = bili_id.parse_page(parsed.query)
    if page and page > 1:
        canonical += "?" + urlencode({"p": page})
    return canonical


def extract_video_id(url: str) -> dict:
    """Scraper-side wrapper of utils.bilibili.extract_video_id raising ScraperError."""
    try:
        return bili_id.extract_video_id(url)
    except bili_id.InvalidBilibiliVideoUrl as e:
        raise ScraperError(str(e)) from e

from __future__ import annotations

import base64
import json
import os
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx
from xhshow import Xhshow

from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.exceptions import ScraperError, ScraperParseError

XHS_API_URL = "https://edith.xiaohongshu.com"
XHS_WEB_URL = "https://www.xiaohongshu.com"
XHS_IMG_CDN = "https://sns-img-hw.xhscdn.com"
XHS_ORIGIN_VIDEO_CDN = "http://sns-video-bd.xhscdn.com"
ACTIVATE_URI = "/api/sns/web/v1/login/activate"
FEED_URI = "/api/sns/web/v1/feed"

PC_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)
PC_HTML_HEADERS = {
    "user-agent": PC_USER_AGENT,
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9",
}
# A mobile UA paired with Chrome's accept header gets redirected to a captcha page,
# so the mobile UA and accept header must match Safari's.
MOBILE_HTML_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SHORT_LINK_HOSTS = ("xhslink.com", "xhslink.cn")
VIDEO_CODECS = ("h264", "h265", "av1", "h266")
GUEST_SESSION_TTL = 30 * 60

_xhshow = Xhshow()
# Module-level guest session cache: (cookies, expires_at)
_guest_session: Dict[str, Any] = {"cookies": None, "expires_at": 0.0}


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def parse_xhs_note_url(note_url: str) -> Dict[str, str]:
    """
    Parse XHS note URL into note_id/xsec_token/xsec_source.
    """
    parsed = urlparse(note_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise ScraperParseError(f"Invalid XHS note URL: {note_url}")
    note_id = path_parts[-1]
    if note_id in {"explore", "discovery", "item"}:
        raise ScraperParseError(f"Invalid XHS note URL path: {note_url}")
    return {
        "note_id": note_id,
        "xsec_token": query.get("xsec_token", ""),
        "xsec_source": query.get("xsec_source", ""),
    }


def get_pure_url(url: str) -> str:
    """
    Get the pure URL without query parameters or fragment.
    """
    parsed = urlparse(url)
    return parsed.scheme + "://" + parsed.netloc + parsed.path


def check_redirect_target(url: str) -> None:
    """Raise a descriptive error when XHS redirected us to a login / risk-control / 404 page."""
    path = urlparse(url).path
    if path.startswith("/login") or "/login" in path:
        raise ScraperError(f"XHS note requires login: {url}")
    if path.startswith("/404/sec"):
        raise ScraperError(f"XHS blocked the request by risk control: {url}")
    if path.startswith("/404"):
        raise ScraperError(f"XHS note does not exist or was deleted: {url}")


def normalize_note_url(url: str) -> str:
    """Add a scheme if missing and map rednote.com note links onto www.xiaohongshu.com."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.netloc.endswith("rednote.com"):
        return parsed._replace(scheme="https", netloc="www.xiaohongshu.com").geturl()
    return url


def parse_cookie_string(cookies: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in (cookies or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def cookie_dict_to_string(cookies: Dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


# ---------------------------------------------------------------------------
# Media helpers
# ---------------------------------------------------------------------------


def _pick(data: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(data, dict):
        return default
    for key in keys:
        if key in data and data.get(key) is not None:
            return data.get(key)
    return default


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def get_trace_id(img_url: str) -> str:
    """Extract the image trace id (path after the 32-hex dir, without `!` processing suffix)."""
    match = re.search(r"/[a-f0-9]{32}/(.*)/([^/!]+)(?:!.*)?", img_url)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    match = re.search(r"/([^/!]+)(?:!.*)?$", img_url)
    if match:
        return match.group(1)
    return img_url


def build_image_url(image: Dict[str, Any]) -> Optional[str]:
    """Return the watermark-free original image URL, falling back to the default URL."""
    trace_id = _pick(image, "trace_id", "traceId")
    if trace_id:
        return f"{XHS_IMG_CDN}/{trace_id}"
    default_url = _pick(image, "url_default", "urlDefault", "url")
    if default_url:
        default_url = str(default_url)
        # Only rewrite XHS CDN URLs; anything else is returned untouched.
        if urlparse(default_url).netloc.endswith("xhscdn.com"):
            trace_id = get_trace_id(default_url)
            if trace_id and trace_id != default_url:
                return f"{XHS_IMG_CDN}/{trace_id}"
        return default_url
    return None


def build_image_thumb_url(image: Dict[str, Any]) -> Optional[str]:
    url = _pick(image, "url_pre", "urlPre")
    if url:
        return str(url)
    for info in _pick(image, "info_list", "infoList", default=[]) or []:
        if isinstance(info, dict) and _pick(info, "image_scene", "imageScene") == "H5_PRV" and info.get("url"):
            return str(info["url"])
    default_url = _pick(image, "url_default", "urlDefault", "url")
    return str(default_url) if default_url else None


def select_stream(stream: Any) -> Optional[Dict[str, Any]]:
    """Pick the first playable stream, preferring broadly compatible codecs."""
    if not isinstance(stream, dict):
        return None
    for codec in VIDEO_CODECS:
        for item in stream.get(codec) or []:
            if isinstance(item, dict) and _pick(item, "master_url", "masterUrl"):
                return item
    return None


# ---------------------------------------------------------------------------
# HTML state parsing
# ---------------------------------------------------------------------------


_INITIAL_STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S)
# The PC page state is a JS object literal, not strict JSON: besides `undefined` it
# contains flat collections such as `"originalCommentIds":new Set([])`.
_JS_FLAT_COLLECTION_RE = re.compile(r"\bnew (?:Set|Map)\((\[[^\[\]]*\])?\)")


def _js_state_to_json(text: str) -> str:
    text = _JS_FLAT_COLLECTION_RE.sub(lambda m: m.group(1) or "[]", text)
    return re.sub(r"\bundefined\b", "null", text)


def parse_initial_state(html: str, note_id: str = "") -> Optional[Dict[str, Any]]:
    """Extract the raw note dict from `window.__INITIAL_STATE__` of a PC or H5 note page."""
    match = _INITIAL_STATE_RE.search(html or "")
    if not match:
        return None
    json_text = _js_state_to_json(match.group(1))
    try:
        state = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    # H5 (mobile) page
    h5 = state.get("noteData")
    if isinstance(h5, dict):
        note = (h5.get("data") or {}).get("noteData")
        if note:
            return note

    # PC page
    pc = state.get("note")
    if isinstance(pc, dict):
        detail_map = pc.get("noteDetailMap") or {}
        entry = detail_map.get(note_id) or detail_map.get(pc.get("firstNoteId") or "") or {}
        note = entry.get("note") if isinstance(entry, dict) else None
        if note:
            return note
    return None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class XhsSinglePostAdapter:
    """Fetch one Xiaohongshu post (and optional comments).

    Requests to edith.xiaohongshu.com are signed locally with `xhshow`. Fetch order:
    1. cookie + feed API (needs a logged-in cookie and an xsec_token)
    2. cookie + PC note page
    3. guest web_session + PC note page
    4. mobile H5 note page without cookies
    """

    def __init__(self, cookies: str = "", timeout: float = 20.0):
        self.cookies = (cookies or "").strip()
        self.cookie_dict = parse_cookie_string(self.cookies)
        self.timeout = timeout
        self._http = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    @property
    def has_login_cookie(self) -> bool:
        return bool(self.cookie_dict.get("a1") and self.cookie_dict.get("web_session"))

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "XhsSinglePostAdapter":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    def _base_headers(self, cookies: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        cookies = self.cookie_dict if cookies is None else cookies
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "origin": XHS_WEB_URL,
            "pragma": "no-cache",
            "referer": f"{XHS_WEB_URL}/",
            "sec-ch-ua": '"Chromium";v="137", "Google Chrome";v="137", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": PC_USER_AGENT,
        }
        if cookies:
            headers["cookie"] = cookie_dict_to_string(cookies)
        return headers

    def _sign_headers(
            self,
            method: str,
            uri: str,
            cookies: Optional[Dict[str, str]] = None,
            params: Optional[Dict[str, Any]] = None,
            payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        cookies = self.cookie_dict if cookies is None else cookies
        if method == "POST":
            sign = _xhshow.sign_headers_post(uri, cookies, payload=payload)
        else:
            sign = _xhshow.sign_headers_get(uri, cookies, params=params)
        headers = self._base_headers(cookies)
        headers.update(sign)
        return headers

    async def _signed_post(
            self, uri: str, data: Dict[str, Any], cookies: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        headers = self._sign_headers("POST", uri, cookies=cookies, payload=data)
        # The body must be byte-identical to what was signed.
        body = _xhshow.build_json_body(data)
        resp = await self._http.post(f"{XHS_API_URL}{uri}", content=body.encode("utf-8"), headers=headers)
        return self._parse_api_response(resp)

    async def _signed_get(
            self, uri: str, params: Optional[Dict[str, Any]] = None, cookies: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        params = params or {}
        headers = self._sign_headers("GET", uri, cookies=cookies, params=params)
        resp = await self._http.get(f"{XHS_API_URL}{uri}", params=params, headers=headers)
        return self._parse_api_response(resp)

    @staticmethod
    def _parse_api_response(resp: httpx.Response) -> Dict[str, Any]:
        if resp.status_code in (461, 471):
            verify_type = resp.headers.get("Verifytype", "")
            verify_uuid = resp.headers.get("Verifyuuid", "")
            raise ScraperError(
                f"XHS blocked by captcha: status={resp.status_code}, "
                f"verify_type={verify_type}, verify_uuid={verify_uuid}"
            )
        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ScraperParseError(f"XHS API returned non-JSON: status={resp.status_code}") from exc

        if body.get("success"):
            return body.get("data", {}) or {}
        raise ScraperParseError(f"XHS API error: status={resp.status_code}, body={body}")

    # -- guest session -----------------------------------------------------

    async def _new_guest_cookies(self) -> Dict[str, str]:
        a1 = _xhshow.generate_a1()
        cookies = {"a1": a1, "webId": _xhshow.generate_web_id(a1), "xsecappid": "xhs-pc-web"}
        payload = {"client_public_key_base64": base64.b64encode(os.urandom(32)).decode()}
        headers = self._sign_headers("POST", ACTIVATE_URI, cookies=cookies, payload=payload)
        resp = await self._http.post(
            f"{XHS_API_URL}{ACTIVATE_URI}",
            content=_xhshow.build_json_body(payload).encode("utf-8"),
            headers=headers,
        )
        web_session = resp.cookies.get("web_session")
        if not web_session:
            raise ScraperError(f"Failed to activate XHS guest session: status={resp.status_code}")
        cookies["web_session"] = web_session
        return cookies

    async def _get_guest_cookies(self) -> Dict[str, str]:
        cached = _guest_session.get("cookies")
        if cached and _guest_session.get("expires_at", 0.0) > time.monotonic():
            return dict(cached)
        cookies = await self._new_guest_cookies()
        _guest_session["cookies"] = dict(cookies)
        _guest_session["expires_at"] = time.monotonic() + GUEST_SESSION_TTL
        return cookies

    @staticmethod
    def _invalidate_guest_cookies() -> None:
        _guest_session["cookies"] = None
        _guest_session["expires_at"] = 0.0

    # -- public API --------------------------------------------------------

    async def fetch_post(
            self,
            note_url: str,
            with_comments: bool = False,
            max_comments: int = 0,
            include_sub_comments: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch one XHS post by full URL (recommended with xsec_token + xsec_source).
        """
        note_url = await self._resolve_note_url(note_url)
        url_info = parse_xhs_note_url(note_url)
        note_id = url_info["note_id"]
        xsec_token = url_info["xsec_token"]
        xsec_source = url_info["xsec_source"]

        stages: List[Tuple[str, Callable[[], Awaitable[Optional[Dict[str, Any]]]]]] = []
        if self.has_login_cookie and xsec_token:
            stages.append(("cookie+feed", lambda: self._fetch_note_by_api(note_id, xsec_token, xsec_source)))
        if self.cookie_dict:
            stages.append(
                ("cookie+html", lambda: self._fetch_note_by_html(note_id, xsec_token, xsec_source, self.cookie_dict))
            )
        stages.append(("guest+html", lambda: self._fetch_note_with_guest(note_id, xsec_token, xsec_source)))
        stages.append(
            ("mobile+html", lambda: self._fetch_note_by_html(note_id, xsec_token, xsec_source, {}, mobile=True))
        )

        note: Optional[Dict[str, Any]] = None
        errors: List[str] = []
        for name, fetch in stages:
            try:
                note = await fetch()
            except Exception as e:
                logger.warning(f"XHS {name} failed for note {note_id}: {e}")
                errors.append(f"{name}: {e}")
                continue
            if note:
                logger.debug(f"XHS note {note_id} fetched via {name}")
                break
            errors.append(f"{name}: empty result")
        if not note:
            raise ScraperError(f"Cannot fetch XHS note {note_id}: " + "; ".join(errors))

        result: Dict[str, Any] = {"platform": "xhs", "note": note, "comments": [], "url": get_pure_url(note_url)}
        if with_comments:
            try:
                result["comments"] = await self._fetch_comments(
                    note_id=note_id,
                    xsec_token=xsec_token,
                    max_comments=max_comments,
                    include_sub_comments=include_sub_comments,
                )
            except Exception as e:
                logger.error(f"Failed to fetch comments for note {note_id}, error: {e}")
                result["comments"] = []
        return result

    async def _fetch_note_by_api(
            self,
            note_id: str,
            xsec_token: str,
            xsec_source: str,
    ) -> Optional[Dict[str, Any]]:
        data: Dict[str, Any] = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": "1"},
        }
        if xsec_token:
            data["xsec_token"] = xsec_token
            data["xsec_source"] = xsec_source or "pc_feed"

        payload = await self._signed_post(FEED_URI, data=data)
        items = payload.get("items", []) or []
        if not items:
            return None
        card = (items[0] or {}).get("note_card", {})
        if not card:
            return None
        card.setdefault("note_id", note_id)
        card["xsec_token"] = xsec_token
        card["xsec_source"] = xsec_source
        return self._normalize_note(card)

    async def _fetch_note_with_guest(
            self, note_id: str, xsec_token: str, xsec_source: str
    ) -> Optional[Dict[str, Any]]:
        cookies = await self._get_guest_cookies()
        try:
            note = await self._fetch_note_by_html(note_id, xsec_token, xsec_source, cookies)
        except Exception:
            self._invalidate_guest_cookies()
            raise
        if note is None:
            self._invalidate_guest_cookies()
        return note

    async def _fetch_note_by_html(
            self,
            note_id: str,
            xsec_token: str,
            xsec_source: str,
            cookies: Optional[Dict[str, str]] = None,
            mobile: bool = False,
    ) -> Optional[Dict[str, Any]]:
        cookies = self.cookie_dict if cookies is None else cookies
        detail_url = f"{XHS_WEB_URL}/explore/{note_id}"
        if xsec_token:
            detail_url += "?" + urlencode({"xsec_token": xsec_token, "xsec_source": xsec_source or "pc_feed"})

        headers = dict(MOBILE_HTML_HEADERS if mobile else PC_HTML_HEADERS)
        if cookies:
            headers["cookie"] = cookie_dict_to_string(cookies)
        resp = await self._http.get(detail_url, headers=headers)
        check_redirect_target(str(resp.url))
        if resp.status_code != 200:
            raise ScraperError(f"XHS note page returned status {resp.status_code}")

        note = parse_initial_state(resp.text, note_id)
        if not note:
            return None
        note.setdefault("noteId", note_id)
        note["xsec_token"] = xsec_token
        note["xsec_source"] = xsec_source
        return self._normalize_note(note)

    async def _fetch_comments(
            self,
            note_id: str,
            xsec_token: str = "",
            max_comments: int = 0,
            include_sub_comments: bool = False,
    ) -> List[Dict[str, Any]]:
        comments: List[Dict[str, Any]] = []
        cursor = ""
        has_more = True

        while has_more:
            params: Dict[str, Any] = {
                "note_id": note_id,
                "cursor": cursor,
                "top_comment_id": "",
                "image_formats": "jpg,webp,avif",
            }
            if xsec_token:
                params["xsec_token"] = xsec_token

            payload = await self._signed_get("/api/sns/web/v2/comment/page", params=params)
            raw_comments = payload.get("comments", []) or []
            for item in raw_comments:
                comments.append(
                    self._normalize_comment(
                        note_id=note_id,
                        note_xsec_token=xsec_token,
                        raw=item,
                        root_comment_id="",
                    )
                )
                if include_sub_comments:
                    comments.extend(
                        await self._fetch_sub_comments(
                            note_id=note_id,
                            root_comment=item,
                            xsec_token=xsec_token,
                        )
                    )
                if max_comments > 0 and len(comments) >= max_comments:
                    return comments[:max_comments]

            has_more = bool(payload.get("has_more", False))
            cursor = str(payload.get("cursor", "") or "")
            if not cursor and has_more:
                break

        return comments

    async def _fetch_sub_comments(
            self,
            note_id: str,
            root_comment: Dict[str, Any],
            xsec_token: str,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        inline_sub_comments = root_comment.get("sub_comments", []) or []
        root_comment_id = str(root_comment.get("id", ""))

        for item in inline_sub_comments:
            results.append(
                self._normalize_comment(
                    note_id=note_id,
                    note_xsec_token=xsec_token,
                    raw=item,
                    root_comment_id=root_comment_id,
                )
            )

        has_more = bool(root_comment.get("sub_comment_has_more", False))
        cursor = str(root_comment.get("sub_comment_cursor", "") or "")
        while has_more:
            params: Dict[str, Any] = {
                "note_id": note_id,
                "root_comment_id": root_comment_id,
                "num": 10,
                "cursor": cursor,
            }
            if xsec_token:
                params["xsec_token"] = xsec_token
            payload = await self._signed_get("/api/sns/web/v2/comment/sub/page", params=params)
            sub_comments = payload.get("comments", []) or []
            for item in sub_comments:
                results.append(
                    self._normalize_comment(
                        note_id=note_id,
                        note_xsec_token=xsec_token,
                        raw=item,
                        root_comment_id=root_comment_id,
                    )
                )
            has_more = bool(payload.get("has_more", False))
            cursor = str(payload.get("cursor", "") or "")
            if not cursor and has_more:
                break
        return results

    def _normalize_note(self, note_item: Dict[str, Any]) -> Dict[str, Any]:
        note_type = str(_pick(note_item, "type", default=""))
        user = _pick(note_item, "user", default={}) or {}
        interact = _pick(note_item, "interact_info", "interactInfo", default={}) or {}
        raw_images = [
            item for item in (_pick(note_item, "image_list", "imageList", default=[]) or []) if isinstance(item, dict)
        ]

        image_list: List[str] = []
        media: List[Dict[str, Any]] = []
        if note_type != "video":
            for item in raw_images:
                url = build_image_url(item)
                if not url:
                    continue
                image_list.append(url)
                entry: Dict[str, Any] = {
                    "type": "image",
                    "url": url,
                    "thumb_url": build_image_thumb_url(item),
                    "video_url": None,
                    "width": _to_int(item.get("width")),
                    "height": _to_int(item.get("height")),
                    "duration": 0,
                }
                if _pick(item, "live_photo", "livePhoto", default=False):
                    stream = select_stream(item.get("stream"))
                    if stream:
                        entry["type"] = "live_photo"
                        entry["video_url"] = str(_pick(stream, "master_url", "masterUrl"))
                media.append(entry)

        tag_list = []
        for tag in _pick(note_item, "tag_list", "tagList", default=[]) or []:
            if not isinstance(tag, dict):
                continue
            if tag.get("type") == "topic" and tag.get("name"):
                tag_list.append(str(tag["name"]))

        video_source = note_item
        video_urls: List[str] = self._extract_video_urls(note_item)
        if not video_urls and isinstance(note_item.get("note"), dict):
            # Some payloads wrap the note body under `note`.
            video_source = note_item["note"]
            video_urls = self._extract_video_urls(video_source)
        if video_urls:
            meta = self._extract_video_meta(video_source)
            cover = build_image_url(raw_images[0]) if raw_images else None
            media.append(
                {
                    "type": "video",
                    "url": video_urls[0],
                    "thumb_url": cover,
                    "video_url": video_urls[0],
                    **meta,
                }
            )

        note_id = str(_pick(note_item, "note_id", "noteId", default=""))
        xsec_token = str(_pick(note_item, "xsec_token", "xsecToken", default=""))
        xsec_source = str(
            _pick(note_item, "xsec_source", "xsecSource", default="pc_search")
            or "pc_search"
        )
        note_url = (
            f"{XHS_WEB_URL}/explore/{note_id}"
            f"?xsec_token={xsec_token}&xsec_source={xsec_source}"
        )

        return {
            "note_id": note_id,
            "type": note_type,
            "title": str(
                _pick(note_item, "title", default="")
                or str(_pick(note_item, "desc", default=""))[:255]
            ),
            "desc": str(_pick(note_item, "desc", default="")),
            "video_urls": video_urls,
            "time": str(_pick(note_item, "time", default="")),
            "last_update_time": str(
                _pick(note_item, "last_update_time", "lastUpdateTime", default="")
            ),
            "ip_location": str(_pick(note_item, "ip_location", "ipLocation", default="")),
            "image_list": image_list,
            "media": media,
            "tag_list": tag_list,
            "url": note_url,
            "note_url": note_url,
            "liked_count": _to_int(_pick(interact, "liked_count", "likedCount", default=0)),
            "collected_count": _to_int(
                _pick(interact, "collected_count", "collectedCount", default=0)
            ),
            "comment_count": _to_int(
                _pick(interact, "comment_count", "commentCount", default=0)
            ),
            "share_count": _to_int(_pick(interact, "share_count", "shareCount", default=0)),
            "user": {
                "user_id": str(_pick(user, "user_id", "userId", default="")),
                "nickname": str(_pick(user, "nickname", "nickName", default="")),
                "avatar": str(_pick(user, "avatar", "image", default="")),
            },
        }

    @staticmethod
    def _extract_video_urls(note_item: Dict[str, Any]) -> List[str]:
        note_type = str(note_item.get("type", "") or "")
        video = note_item.get("video", {}) or {}
        if note_type != "video" and not isinstance(video, dict):
            return []

        consumer = video.get("consumer", {}) or {}
        origin_video_key = consumer.get("origin_video_key") or consumer.get("originVideoKey")
        if origin_video_key:
            return [f"{XHS_ORIGIN_VIDEO_CDN}/{origin_video_key}"]

        urls: List[str] = []
        stream = (video.get("media", {}) or {}).get("stream", {}) or {}
        # Prefer broadly compatible streams first, then fallback to newer codecs.
        for stream_key in VIDEO_CODECS:
            for item in stream.get(stream_key, []) or []:
                if not isinstance(item, dict):
                    continue
                master_url = item.get("master_url") or item.get("masterUrl")
                if master_url:
                    urls.append(str(master_url))
                for backup_url in item.get("backup_urls", []) or item.get("backupUrls", []) or []:
                    if backup_url:
                        urls.append(str(backup_url))

        # Keep ordering while deduplicating.
        seen = set()
        deduped: List[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    @staticmethod
    def _extract_video_meta(note_item: Dict[str, Any]) -> Dict[str, int]:
        """Width/height/duration (seconds) of the preferred video stream."""
        video = note_item.get("video", {}) or {}
        if not isinstance(video, dict):
            video = {}
        stream = select_stream((video.get("media", {}) or {}).get("stream", {}))
        meta = {"width": 0, "height": 0, "duration": 0}
        if stream:
            meta["width"] = _to_int(stream.get("width"))
            meta["height"] = _to_int(stream.get("height"))
            duration_ms = _to_int(stream.get("duration"))
            meta["duration"] = duration_ms // 1000 if duration_ms > 1000 else duration_ms
        if not meta["duration"]:
            capa = video.get("capa", {}) or {}
            meta["duration"] = _to_int(capa.get("duration"))
        return meta

    def _normalize_comment(
            self,
            note_id: str,
            note_xsec_token: str,
            raw: Dict[str, Any],
            root_comment_id: str = "",
    ) -> Dict[str, Any]:
        user = raw.get("user_info", {}) or {}
        target = raw.get("target_comment", {}) or {}
        pics = []
        for item in raw.get("pictures", []) or []:
            url = item.get("url_default")
            if url:
                pics.append(url)

        return {
            "comment_id": str(raw.get("id", "")),
            "parent_comment_id": root_comment_id,
            "target_comment_id": str(target.get("id", "")),
            "note_id": note_id,
            "content": str(raw.get("content", "")),
            "create_time": str(raw.get("create_time", "")),
            "ip_location": str(raw.get("ip_location", "")),
            "sub_comment_count": int(raw.get("sub_comment_count", 0) or 0),
            "like_count": int(raw.get("like_count", 0) or 0),
            "pictures": pics,
            "note_url": (
                f"{XHS_WEB_URL}/explore/{note_id}"
                f"?xsec_token={note_xsec_token}&xsec_source=pc_search"
            ),
            "user": {
                "user_id": str(user.get("user_id", "")),
                "nickname": str(user.get("nickname", "")),
                "avatar": str(user.get("image", "")),
            },
        }

    async def _resolve_note_url(self, note_url: str) -> str:
        """Normalize the input and follow short-link redirects to a xiaohongshu.com note URL."""
        note_url = normalize_note_url(note_url.strip())
        host = urlparse(note_url).netloc
        if host.endswith("xiaohongshu.com"):
            check_redirect_target(note_url)
            return note_url

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.get(note_url, headers=MOBILE_HTML_HEADERS)

        # XHS may land on www.rednote.com; map it back onto xiaohongshu.com.
        final_url = normalize_note_url(str(resp.url))
        if not urlparse(final_url).netloc.endswith("xiaohongshu.com"):
            raise ScraperError(
                f"Short URL did not redirect to xiaohongshu.com: {note_url} -> {final_url}"
            )
        check_redirect_target(final_url)
        if not [p for p in urlparse(final_url).path.split("/") if p]:
            raise ScraperError(f"Short URL redirected to XHS home page (expired link?): {note_url}")
        return final_url

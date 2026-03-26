from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx

from fastfetchbot_shared.config import settings as shared_settings
from fastfetchbot_shared.utils.logger import logger

XHS_API_URL = "https://edith.xiaohongshu.com"
XHS_WEB_URL = "https://www.xiaohongshu.com"


def parse_xhs_note_url(note_url: str) -> Dict[str, str]:
    """
    Parse XHS note URL into note_id/xsec_token/xsec_source.
    """
    parsed = urlparse(note_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise ValueError(f"Invalid XHS note URL: {note_url}")
    note_id = path_parts[-1]
    if note_id in {"explore", "discovery", "item"}:
        raise ValueError(f"Invalid XHS note URL path: {note_url}")
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


class XhsSinglePostAdapter:
    """Small adapter for fetching one Xiaohongshu post and optional comments."""

    def __init__(
            self,
            cookies: str,
            sign_server_endpoint: str = "",
            timeout: float = 20.0,
    ):
        self.cookies = cookies.strip()
        self.sign_server_endpoint = (sign_server_endpoint or shared_settings.SIGN_SERVER_URL).rstrip("/")
        if not self.sign_server_endpoint:
            raise ValueError(
                "XhsSinglePostAdapter requires a sign server URL. "
                "Set shared_settings.SIGN_SERVER_URL in the environment or pass sign_server_endpoint explicitly."
            )
        self.timeout = timeout
        self._http = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "XhsSinglePostAdapter":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    def _base_headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "origin": XHS_WEB_URL,
            "pragma": "no-cache",
            "referer": f"{XHS_WEB_URL}/",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
            "cookie": self.cookies,
        }

    async def _sign_headers(self, uri: str, data: Optional[Any] = None) -> Dict[str, str]:
        payload = {"uri": uri, "data": data, "cookies": self.cookies}
        resp = await self._http.post(
            f"{self.sign_server_endpoint}/signsrv/v1/xhs/sign",
            json=payload,
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("isok"):
            raise RuntimeError(f"XHS sign server returned error: {body}")
        sign = body.get("data", {}) or {}
        required = ["x_s", "x_t", "x_s_common", "x_b3_traceid"]
        missing = [key for key in required if key not in sign]
        if missing:
            raise RuntimeError(f"XHS sign response missing fields: {missing}")
        headers = self._base_headers()
        headers.update(
            {
                "X-s": sign["x_s"],
                "X-t": sign["x_t"],
                "x-s-common": sign["x_s_common"],
                "X-B3-Traceid": sign["x_b3_traceid"],
            }
        )
        return headers

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
        if not note_url.startswith(XHS_WEB_URL):
            note_url = await self._get_redirection_url(note_url)
        url_info = parse_xhs_note_url(note_url)
        try:
            note = await self._fetch_note_by_api(
                note_id=url_info["note_id"],
                xsec_token=url_info["xsec_token"],
                xsec_source=url_info["xsec_source"],
            )
        except Exception as e:
            logger.error(f"Failed to fetch note by API: {url_info['note_id']}, error: {e}")
            note = None

        if note is None:
            note = await self._fetch_note_by_html(
                note_id=url_info["note_id"],
                xsec_token=url_info["xsec_token"],
                xsec_source=url_info["xsec_source"],
            )
        if note is None:
            raise RuntimeError(f"Cannot fetch note detail from API or HTML: {url_info['note_id']}")

        result: Dict[str, Any] = {"platform": "xhs", "note": note, "comments": [], "url": get_pure_url(note_url)}
        if with_comments:
            try:
                result["comments"] = await self._fetch_comments(
                    note_id=url_info["note_id"],
                    xsec_token=url_info["xsec_token"],
                    max_comments=max_comments,
                    include_sub_comments=include_sub_comments,
                )
            except Exception as e:
                logger.error(f"Failed to fetch comments for note {url_info['note_id']}, error: {e}")
                result["comments"] = []
        return result

    async def _signed_post(self, uri: str, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = await self._sign_headers(uri=uri, data=data)
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        resp = await self._http.post(
            f"{XHS_API_URL}{uri}",
            content=json_str.encode("utf-8"),
            headers=headers,
        )
        return self._parse_api_response(resp)

    async def _signed_get(self, uri: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        final_uri = uri
        if params:
            final_uri = f"{uri}?{urlencode(params, doseq=True)}"
        headers = await self._sign_headers(uri=final_uri)
        resp = await self._http.get(
            f"{XHS_API_URL}{uri}",
            params=params,
            headers=headers,
        )
        return self._parse_api_response(resp)

    @staticmethod
    def _parse_api_response(resp: httpx.Response) -> Dict[str, Any]:
        try:
            body = resp.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"XHS API returned non-JSON: status={resp.status_code}") from exc

        if resp.status_code in (461, 471):
            verify_type = resp.headers.get("Verifytype", "")
            verify_uuid = resp.headers.get("Verifyuuid", "")
            raise RuntimeError(
                f"XHS blocked by captcha: verify_type={verify_type}, verify_uuid={verify_uuid}"
            )

        if body.get("success"):
            return body.get("data", {}) or {}
        raise RuntimeError(f"XHS API error: status={resp.status_code}, body={body}")

    async def _fetch_note_by_api(
            self,
            note_id: str,
            xsec_token: str,
            xsec_source: str,
    ) -> Optional[Dict[str, Any]]:
        data: Dict[str, Any] = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
        }
        if xsec_token:
            data["xsec_token"] = xsec_token
            data["xsec_source"] = xsec_source

        payload = await self._signed_post("/api/sns/web/v1/feed", data=data)
        items = payload.get("items", []) or []
        if not items:
            return None
        card = (items[0] or {}).get("note_card", {})
        if not card:
            return None
        card["xsec_token"] = xsec_token
        card["xsec_source"] = xsec_source
        return self._normalize_note(card)

    async def _fetch_note_by_html(
            self,
            note_id: str,
            xsec_token: str,
            xsec_source: str,
    ) -> Optional[Dict[str, Any]]:
        detail_url = f"{XHS_WEB_URL}/explore/{note_id}"
        if xsec_token:
            detail_url += f"?xsec_token={xsec_token}&xsec_source={xsec_source}"

        resp = await self._http.get(detail_url, headers=self._base_headers())
        if resp.status_code != 200:
            return None

        text = resp.text or ""
        match = re.search(r"window.__INITIAL_STATE__=({.*})</script>", text)
        if not match:
            return None

        try:
            state = json.loads(match.group(1).replace("undefined", "null"))
            note = (
                state.get("note", {})
                .get("noteDetailMap", {})
                .get(note_id, {})
                .get("note")
            )
        except json.JSONDecodeError:
            return None

        if not note:
            return None
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
        def _pick(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
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

        note_type = str(_pick(note_item, "type", default=""))
        user = _pick(note_item, "user", default={}) or {}
        interact = _pick(note_item, "interact_info", "interactInfo", default={}) or {}
        image_list = []
        if note_type != "video":
            for item in _pick(note_item, "image_list", "imageList", default=[]) or []:
                url = (
                    _pick(item, "url_default", "urlDefault", "url")
                    if isinstance(item, dict)
                    else None
                )
                if url:
                    image_list.append(str(url))

        tag_list = []
        for tag in _pick(note_item, "tag_list", "tagList", default=[]) or []:
            if not isinstance(tag, dict):
                continue
            if tag.get("type") == "topic" and tag.get("name"):
                tag_list.append(str(tag["name"]))

        video_urls: List[str] = self._extract_video_urls(note_item)
        if not video_urls and isinstance(note_item.get("note"), dict):
            # Some payloads wrap the note body under `note`.
            video_urls = self._extract_video_urls(note_item["note"])
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
                "nickname": str(_pick(user, "nickname", default="")),
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
            return [f"http://sns-video-bd.xhscdn.com/{origin_video_key}"]

        urls: List[str] = []
        stream = (video.get("media", {}) or {}).get("stream", {}) or {}
        # Prefer broadly compatible streams first, then fallback to newer codecs.
        for stream_key in ("h264", "h265", "av1", "h266"):
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

    async def _get_redirection_url(self, note_url: str) -> str:
        """Follow redirects from a short URL (e.g. xhslink.com) to the full xiaohongshu.com URL."""
        redirect_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.get(note_url, headers=redirect_headers)

        final_url = str(resp.url)
        if XHS_WEB_URL not in final_url and "xiaohongshu.com" not in final_url:
            raise RuntimeError(
                f"Short URL did not redirect to xiaohongshu.com: {note_url} -> {final_url}"
            )
        return final_url

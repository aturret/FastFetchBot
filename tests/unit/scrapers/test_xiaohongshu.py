"""Unit tests for Xiaohongshu scraper and adapter modules.

Covers:
- packages/shared/fastfetchbot_shared/services/scrapers/xiaohongshu/__init__.py
- packages/shared/fastfetchbot_shared/services/scrapers/xiaohongshu/adaptar.py
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import httpx

from fastfetchbot_shared.services.scrapers.xiaohongshu.adaptar import (
    XhsSinglePostAdapter,
    parse_xhs_note_url,
    get_pure_url,
    XHS_API_URL,
    XHS_WEB_URL,
)
from fastfetchbot_shared.models.metadata_item import MessageType, MediaFile
from fastfetchbot_shared.exceptions import ScraperError, ScraperParseError, ExternalServiceError


# ---------------------------------------------------------------------------
# Module-level function tests
# ---------------------------------------------------------------------------

class TestParseXhsNoteUrl:
    """Tests for parse_xhs_note_url."""

    def test_basic_url(self):
        url = "https://www.xiaohongshu.com/explore/abc123?xsec_token=tok&xsec_source=src"
        result = parse_xhs_note_url(url)
        assert result["note_id"] == "abc123"
        assert result["xsec_token"] == "tok"
        assert result["xsec_source"] == "src"

    def test_url_without_query(self):
        url = "https://www.xiaohongshu.com/explore/abc123"
        result = parse_xhs_note_url(url)
        assert result["note_id"] == "abc123"
        assert result["xsec_token"] == ""
        assert result["xsec_source"] == ""

    def test_nested_path(self):
        url = "https://www.xiaohongshu.com/discovery/item/note456"
        result = parse_xhs_note_url(url)
        assert result["note_id"] == "note456"

    def test_empty_path_raises(self):
        with pytest.raises(ScraperParseError, match="Invalid XHS note URL"):
            parse_xhs_note_url("https://www.xiaohongshu.com/")

    def test_explore_only_raises(self):
        with pytest.raises(ScraperParseError, match="Invalid XHS note URL path"):
            parse_xhs_note_url("https://www.xiaohongshu.com/explore")

    def test_discovery_only_raises(self):
        with pytest.raises(ScraperParseError, match="Invalid XHS note URL path"):
            parse_xhs_note_url("https://www.xiaohongshu.com/discovery")

    def test_item_only_raises(self):
        with pytest.raises(ScraperParseError, match="Invalid XHS note URL path"):
            parse_xhs_note_url("https://www.xiaohongshu.com/item")


class TestGetPureUrl:
    """Tests for get_pure_url."""

    def test_strips_query_and_fragment(self):
        url = "https://www.xiaohongshu.com/explore/abc?xsec_token=t#frag"
        assert get_pure_url(url) == "https://www.xiaohongshu.com/explore/abc"

    def test_url_without_query(self):
        url = "https://www.xiaohongshu.com/explore/abc"
        assert get_pure_url(url) == url


# ---------------------------------------------------------------------------
# XhsSinglePostAdapter tests
# ---------------------------------------------------------------------------

class TestXhsSinglePostAdapterInit:
    """Tests for XhsSinglePostAdapter.__init__."""

    def test_basic_init(self):
        adapter = XhsSinglePostAdapter(
            cookies="  a=1; b=2  ",
            sign_server_endpoint="http://sign:8989",
        )
        assert adapter.cookies == "a=1; b=2"
        assert adapter.sign_server_endpoint == "http://sign:8989"
        assert adapter.timeout == 20.0

    def test_strips_trailing_slash(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1",
            sign_server_endpoint="http://sign:8989/",
        )
        assert adapter.sign_server_endpoint == "http://sign:8989"

    @patch("fastfetchbot_shared.config.settings.SIGN_SERVER_URL", "")
    def test_no_sign_server_raises(self):
        with pytest.raises(ExternalServiceError, match="sign server URL"):
            XhsSinglePostAdapter(cookies="c=1", sign_server_endpoint="")

    @patch("fastfetchbot_shared.config.settings.SIGN_SERVER_URL", "http://fallback:8989")
    def test_fallback_to_env_sign_server(self):
        adapter = XhsSinglePostAdapter(cookies="c=1", sign_server_endpoint="")
        assert adapter.sign_server_endpoint == "http://fallback:8989"

    def test_custom_timeout(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989", timeout=5.0
        )
        assert adapter.timeout == 5.0


class TestXhsSinglePostAdapterContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_aenter_aexit(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        adapter._http = AsyncMock()
        async with adapter as a:
            assert a is adapter
        adapter._http.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        adapter._http = AsyncMock()
        await adapter.close()
        adapter._http.aclose.assert_awaited_once()


class TestBaseHeaders:
    """Tests for _base_headers."""

    def test_returns_expected_keys(self):
        adapter = XhsSinglePostAdapter(
            cookies="mycookie=val", sign_server_endpoint="http://s:8989"
        )
        headers = adapter._base_headers()
        assert headers["cookie"] == "mycookie=val"
        assert headers["origin"] == XHS_WEB_URL
        assert "user-agent" in headers
        assert headers["content-type"] == "application/json;charset=UTF-8"


class TestSignHeaders:
    """Tests for _sign_headers."""

    @pytest.mark.asyncio
    async def test_success(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "isok": True,
            "data": {
                "x_s": "xs_val",
                "x_t": "xt_val",
                "x_s_common": "xsc_val",
                "x_b3_traceid": "trace_val",
            },
        }
        mock_resp.raise_for_status = MagicMock()
        adapter._http = AsyncMock()
        adapter._http.post = AsyncMock(return_value=mock_resp)

        headers = await adapter._sign_headers("/api/test")
        assert headers["X-s"] == "xs_val"
        assert headers["X-t"] == "xt_val"
        assert headers["x-s-common"] == "xsc_val"
        assert headers["X-B3-Traceid"] == "trace_val"
        assert headers["cookie"] == "c=1"

    @pytest.mark.asyncio
    async def test_not_ok_raises(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"isok": False, "error": "bad"}
        mock_resp.raise_for_status = MagicMock()
        adapter._http = AsyncMock()
        adapter._http.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(ExternalServiceError, match="sign server returned error"):
            await adapter._sign_headers("/api/test")

    @pytest.mark.asyncio
    async def test_missing_fields_raises(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "isok": True,
            "data": {"x_s": "xs_val"},  # missing x_t, x_s_common, x_b3_traceid
        }
        mock_resp.raise_for_status = MagicMock()
        adapter._http = AsyncMock()
        adapter._http.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(ExternalServiceError, match="missing fields"):
            await adapter._sign_headers("/api/test")

    @pytest.mark.asyncio
    async def test_none_data_uses_empty_dict(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"isok": True, "data": None}
        mock_resp.raise_for_status = MagicMock()
        adapter._http = AsyncMock()
        adapter._http.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(ExternalServiceError, match="missing fields"):
            await adapter._sign_headers("/api/test")

    @pytest.mark.asyncio
    async def test_sign_headers_with_data_param(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "isok": True,
            "data": {
                "x_s": "a", "x_t": "b", "x_s_common": "c", "x_b3_traceid": "d",
            },
        }
        mock_resp.raise_for_status = MagicMock()
        adapter._http = AsyncMock()
        adapter._http.post = AsyncMock(return_value=mock_resp)

        await adapter._sign_headers("/api/test", data={"key": "val"})
        call_args = adapter._http.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["data"] == {"key": "val"}


class TestParseApiResponse:
    """Tests for _parse_api_response static method."""

    def _make_response(self, status_code, body, headers=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.json.return_value = body
        resp.headers = headers or {}
        return resp

    def test_success(self):
        resp = self._make_response(200, {"success": True, "data": {"key": "val"}})
        result = XhsSinglePostAdapter._parse_api_response(resp)
        assert result == {"key": "val"}

    def test_success_no_data(self):
        resp = self._make_response(200, {"success": True, "data": None})
        result = XhsSinglePostAdapter._parse_api_response(resp)
        assert result == {}

    def test_non_json_raises(self):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.side_effect = json.JSONDecodeError("err", "", 0)
        with pytest.raises(ScraperParseError, match="non-JSON"):
            XhsSinglePostAdapter._parse_api_response(resp)

    def test_captcha_461(self):
        resp = self._make_response(
            461, {"success": False},
            headers={"Verifytype": "captcha", "Verifyuuid": "uuid1"},
        )
        with pytest.raises(ScraperError, match="captcha"):
            XhsSinglePostAdapter._parse_api_response(resp)

    def test_captcha_471(self):
        resp = self._make_response(
            471, {"success": False},
            headers={"Verifytype": "sms", "Verifyuuid": "uuid2"},
        )
        with pytest.raises(ScraperError, match="captcha"):
            XhsSinglePostAdapter._parse_api_response(resp)

    def test_api_error_not_success(self):
        resp = self._make_response(200, {"success": False, "msg": "error"})
        with pytest.raises(ScraperParseError, match="XHS API error"):
            XhsSinglePostAdapter._parse_api_response(resp)


class TestExtractVideoUrls:
    """Tests for _extract_video_urls static method."""

    def test_non_video_type_no_video_dict(self):
        result = XhsSinglePostAdapter._extract_video_urls({"type": "normal", "video": "not_a_dict"})
        assert result == []

    def test_origin_video_key(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {"origin_video_key": "key123"},
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == ["http://sns-video-bd.xhscdn.com/key123"]

    def test_origin_video_key_camel_case(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {"originVideoKey": "key456"},
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == ["http://sns-video-bd.xhscdn.com/key456"]

    def test_stream_h264(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {},
                "media": {
                    "stream": {
                        "h264": [
                            {
                                "master_url": "https://h264.mp4",
                                "backup_urls": ["https://h264_backup.mp4"],
                            }
                        ]
                    }
                },
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert "https://h264.mp4" in result
        assert "https://h264_backup.mp4" in result

    def test_stream_deduplication(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {},
                "media": {
                    "stream": {
                        "h264": [
                            {"master_url": "https://same.mp4", "backup_urls": ["https://same.mp4"]},
                        ]
                    }
                },
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == ["https://same.mp4"]

    def test_stream_multiple_codecs(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {},
                "media": {
                    "stream": {
                        "h264": [{"master_url": "https://h264.mp4"}],
                        "h265": [{"master_url": "https://h265.mp4"}],
                        "av1": [{"masterUrl": "https://av1.mp4"}],
                    }
                },
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert "https://h264.mp4" in result
        assert "https://h265.mp4" in result
        assert "https://av1.mp4" in result

    def test_empty_video(self):
        note = {"type": "video", "video": {}}
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == []

    def test_no_video_key(self):
        note = {"type": "normal"}
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == []

    def test_video_none(self):
        note = {"type": "video", "video": None}
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == []

    def test_non_dict_item_in_stream(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {},
                "media": {"stream": {"h264": ["not_a_dict"]}},
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == []

    def test_backup_urls_camel_case(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {},
                "media": {
                    "stream": {
                        "h264": [
                            {"master_url": "https://main.mp4", "backupUrls": ["https://backup.mp4"]},
                        ]
                    }
                },
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert "https://backup.mp4" in result

    def test_empty_backup_url_skipped(self):
        note = {
            "type": "video",
            "video": {
                "consumer": {},
                "media": {
                    "stream": {
                        "h264": [
                            {"master_url": "https://main.mp4", "backup_urls": ["", None]},
                        ]
                    }
                },
            },
        }
        result = XhsSinglePostAdapter._extract_video_urls(note)
        assert result == ["https://main.mp4"]


class TestNormalizeNote:
    """Tests for _normalize_note."""

    def _make_adapter(self):
        return XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )

    def _make_note(self, **overrides):
        note = {
            "type": "normal",
            "note_id": "n123",
            "title": "Test Title",
            "desc": "Test desc",
            "time": "1700000000",
            "last_update_time": "1700001000",
            "ip_location": "Beijing",
            "user": {"user_id": "u1", "nickname": "Nick", "avatar": "https://avatar.jpg"},
            "interact_info": {
                "liked_count": "10",
                "collected_count": "5",
                "comment_count": "3",
                "share_count": "2",
            },
            "image_list": [{"url_default": "https://img1.jpg"}, {"url": "https://img2.jpg"}],
            "tag_list": [{"type": "topic", "name": "tag1"}, {"type": "other", "name": "skip"}],
            "xsec_token": "tok",
            "xsec_source": "src",
        }
        note.update(overrides)
        return note

    def test_basic_normalize(self):
        adapter = self._make_adapter()
        result = adapter._normalize_note(self._make_note())
        assert result["note_id"] == "n123"
        assert result["title"] == "Test Title"
        assert result["desc"] == "Test desc"
        assert result["liked_count"] == 10
        assert result["collected_count"] == 5
        assert result["comment_count"] == 3
        assert result["share_count"] == 2
        assert result["ip_location"] == "Beijing"
        assert result["user"]["nickname"] == "Nick"
        assert "https://img1.jpg" in result["image_list"]
        assert "https://img2.jpg" in result["image_list"]
        assert "tag1" in result["tag_list"]
        assert "skip" not in result["tag_list"]
        assert result["video_urls"] == []

    def test_video_type_skips_images(self):
        adapter = self._make_adapter()
        note = self._make_note(type="video")
        result = adapter._normalize_note(note)
        assert result["image_list"] == []

    def test_video_urls_from_nested_note(self):
        adapter = self._make_adapter()
        note = self._make_note(type="video")
        note["video"] = {}  # No video data at top level
        note["note"] = {
            "type": "video",
            "video": {"consumer": {"origin_video_key": "vk1"}},
        }
        result = adapter._normalize_note(note)
        assert result["video_urls"] == ["http://sns-video-bd.xhscdn.com/vk1"]

    def test_missing_title_uses_desc(self):
        adapter = self._make_adapter()
        note = self._make_note(title="")
        result = adapter._normalize_note(note)
        assert result["title"] == "Test desc"

    def test_none_user(self):
        adapter = self._make_adapter()
        note = self._make_note(user=None)
        result = adapter._normalize_note(note)
        assert result["user"]["nickname"] == ""

    def test_non_dict_tag_skipped(self):
        adapter = self._make_adapter()
        note = self._make_note(tag_list=["not_a_dict", {"type": "topic", "name": "good"}])
        result = adapter._normalize_note(note)
        assert result["tag_list"] == ["good"]

    def test_tag_without_name_skipped(self):
        adapter = self._make_adapter()
        note = self._make_note(tag_list=[{"type": "topic"}])
        result = adapter._normalize_note(note)
        assert result["tag_list"] == []

    def test_to_int_handles_bad_values(self):
        adapter = self._make_adapter()
        note = self._make_note()
        note["interact_info"]["liked_count"] = "not_a_number"
        result = adapter._normalize_note(note)
        assert result["liked_count"] == 0

    def test_to_int_handles_none(self):
        adapter = self._make_adapter()
        note = self._make_note()
        note["interact_info"]["liked_count"] = None
        result = adapter._normalize_note(note)
        assert result["liked_count"] == 0

    def test_xsec_source_defaults_to_pc_search(self):
        adapter = self._make_adapter()
        note = self._make_note(xsec_source=None)
        result = adapter._normalize_note(note)
        assert "pc_search" in result["url"]

    def test_none_image_list(self):
        adapter = self._make_adapter()
        note = self._make_note(image_list=None)
        result = adapter._normalize_note(note)
        assert result["image_list"] == []

    def test_image_item_without_url(self):
        adapter = self._make_adapter()
        note = self._make_note(image_list=[{"no_url_key": True}])
        result = adapter._normalize_note(note)
        assert result["image_list"] == []

    def test_non_dict_image_item(self):
        adapter = self._make_adapter()
        note = self._make_note(image_list=["just_a_string"])
        result = adapter._normalize_note(note)
        assert result["image_list"] == []

    def test_camel_case_keys(self):
        adapter = self._make_adapter()
        note = {
            "type": "normal",
            "noteId": "n789",
            "title": "Camel",
            "desc": "",
            "time": "",
            "lastUpdateTime": "",
            "ipLocation": "Shanghai",
            "user": {"userId": "u2", "nickname": "Nick2", "image": "https://av2.jpg"},
            "interactInfo": {
                "likedCount": "20",
                "collectedCount": "15",
                "commentCount": "7",
                "shareCount": "4",
            },
            "imageList": [{"urlDefault": "https://camelimg.jpg"}],
            "tagList": [{"type": "topic", "name": "cameltag"}],
            "xsecToken": "ctok",
            "xsecSource": "csrc",
        }
        result = adapter._normalize_note(note)
        assert result["note_id"] == "n789"
        assert result["ip_location"] == "Shanghai"
        assert result["liked_count"] == 20
        assert "https://camelimg.jpg" in result["image_list"]
        assert "cameltag" in result["tag_list"]
        assert result["user"]["avatar"] == "https://av2.jpg"

    def test_pick_returns_default_for_non_dict(self):
        """_pick with non-dict data returns default."""
        adapter = self._make_adapter()
        # interact_info as a non-dict
        note = self._make_note()
        note["interact_info"] = "not_a_dict"
        result = adapter._normalize_note(note)
        assert result["liked_count"] == 0


class TestNormalizeComment:
    """Tests for _normalize_comment."""

    def _make_adapter(self):
        return XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )

    def test_basic_comment(self):
        adapter = self._make_adapter()
        raw = {
            "id": "c1",
            "content": "nice post",
            "create_time": "1700000000",
            "ip_location": "Shanghai",
            "sub_comment_count": 3,
            "like_count": 10,
            "user_info": {"user_id": "u1", "nickname": "User1", "image": "https://av.jpg"},
            "target_comment": {"id": "tc1"},
            "pictures": [{"url_default": "https://pic1.jpg"}, {"url_default": ""}],
        }
        result = adapter._normalize_comment(
            note_id="n1", note_xsec_token="tok", raw=raw, root_comment_id="root1"
        )
        assert result["comment_id"] == "c1"
        assert result["parent_comment_id"] == "root1"
        assert result["target_comment_id"] == "tc1"
        assert result["content"] == "nice post"
        assert result["sub_comment_count"] == 3
        assert result["like_count"] == 10
        assert result["pictures"] == ["https://pic1.jpg"]
        assert result["user"]["nickname"] == "User1"

    def test_empty_user_info(self):
        adapter = self._make_adapter()
        raw = {"id": "c2", "user_info": None, "target_comment": None, "pictures": None}
        result = adapter._normalize_comment(
            note_id="n1", note_xsec_token="", raw=raw
        )
        assert result["user"]["user_id"] == ""
        assert result["target_comment_id"] == ""
        assert result["pictures"] == []


class TestFetchNoteByApi:
    """Tests for _fetch_note_by_api."""

    def _make_adapter(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        return adapter

    @pytest.mark.asyncio
    async def test_success_with_xsec_token(self):
        adapter = self._make_adapter()
        note_card = {
            "type": "normal",
            "note_id": "n1",
            "title": "T",
            "desc": "",
            "user": {"user_id": "u1", "nickname": "N", "avatar": ""},
            "interact_info": {},
        }
        adapter._signed_post = AsyncMock(return_value={
            "items": [{"note_card": note_card}]
        })
        result = await adapter._fetch_note_by_api("n1", "tok", "src")
        assert result is not None
        assert result["note_id"] == "n1"

    @pytest.mark.asyncio
    async def test_no_xsec_token(self):
        adapter = self._make_adapter()
        note_card = {
            "type": "normal",
            "note_id": "n1",
            "title": "T",
            "desc": "",
            "user": {},
            "interact_info": {},
        }
        adapter._signed_post = AsyncMock(return_value={
            "items": [{"note_card": note_card}]
        })
        result = await adapter._fetch_note_by_api("n1", "", "")
        assert result is not None
        # Verify xsec_token not in the POST data
        call_data = adapter._signed_post.call_args.kwargs.get("data") or adapter._signed_post.call_args[1].get("data")
        assert "xsec_token" not in call_data

    @pytest.mark.asyncio
    async def test_empty_items_returns_none(self):
        adapter = self._make_adapter()
        adapter._signed_post = AsyncMock(return_value={"items": []})
        result = await adapter._fetch_note_by_api("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_none_items_returns_none(self):
        adapter = self._make_adapter()
        adapter._signed_post = AsyncMock(return_value={"items": None})
        result = await adapter._fetch_note_by_api("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_note_card_returns_none(self):
        adapter = self._make_adapter()
        adapter._signed_post = AsyncMock(return_value={"items": [{"note_card": {}}]})
        result = await adapter._fetch_note_by_api("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_none_first_item(self):
        adapter = self._make_adapter()
        adapter._signed_post = AsyncMock(return_value={"items": [None]})
        result = await adapter._fetch_note_by_api("n1", "tok", "src")
        assert result is None


class TestFetchNoteByHtml:
    """Tests for _fetch_note_by_html."""

    def _make_adapter(self):
        return XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )

    @pytest.mark.asyncio
    async def test_success(self):
        adapter = self._make_adapter()
        state = {
            "note": {
                "noteDetailMap": {
                    "n1": {
                        "note": {
                            "type": "normal",
                            "note_id": "n1",
                            "title": "HTML Title",
                            "desc": "",
                            "user": {},
                            "interact_info": {},
                        }
                    }
                }
            }
        }
        html_text = f'<html>window.__INITIAL_STATE__={json.dumps(state)}</script></html>'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_text
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._fetch_note_by_html("n1", "tok", "src")
        assert result is not None
        assert result["note_id"] == "n1"

    @pytest.mark.asyncio
    async def test_with_xsec_token_in_url(self):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        state = {"note": {"noteDetailMap": {"n1": {"note": {
            "type": "normal", "note_id": "n1", "title": "T", "desc": "",
            "user": {}, "interact_info": {},
        }}}}}
        mock_resp.text = f'window.__INITIAL_STATE__={json.dumps(state)}</script>'
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        await adapter._fetch_note_by_html("n1", "tok_val", "src_val")
        call_url = adapter._http.get.call_args[0][0]
        assert "xsec_token=tok_val" in call_url

    @pytest.mark.asyncio
    async def test_no_xsec_token(self):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        state = {"note": {"noteDetailMap": {"n1": {"note": {
            "type": "normal", "note_id": "n1", "title": "T", "desc": "",
            "user": {}, "interact_info": {},
        }}}}}
        mock_resp.text = f'window.__INITIAL_STATE__={json.dumps(state)}</script>'
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        await adapter._fetch_note_by_html("n1", "", "")
        call_url = adapter._http.get.call_args[0][0]
        assert "xsec_token" not in call_url

    @pytest.mark.asyncio
    async def test_non_200_returns_none(self):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._fetch_note_by_html("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_initial_state_returns_none(self):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>no state here</html>"
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._fetch_note_by_html("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = 'window.__INITIAL_STATE__={not valid json}</script>'
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._fetch_note_by_html("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_note_not_found_in_map_returns_none(self):
        adapter = self._make_adapter()
        state = {"note": {"noteDetailMap": {"other_id": {"note": {}}}}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = f'window.__INITIAL_STATE__={json.dumps(state)}</script>'
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._fetch_note_by_html("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_text(self):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = ""
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._fetch_note_by_html("n1", "tok", "src")
        assert result is None

    @pytest.mark.asyncio
    async def test_undefined_replaced_with_null(self):
        """The method replaces 'undefined' with 'null' in the JSON."""
        adapter = self._make_adapter()
        state_str = '{"note":{"noteDetailMap":{"n1":{"note":{"type":"normal","note_id":"n1","title":"T","desc":"","user":{},"interact_info":{},"some_field":undefined}}}}}'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = f'window.__INITIAL_STATE__={state_str}</script>'
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._fetch_note_by_html("n1", "", "")
        assert result is not None


class TestFetchPost:
    """Tests for fetch_post."""

    def _make_adapter(self):
        return XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )

    def _make_normalized_note(self, note_id="n1"):
        return {
            "note_id": note_id,
            "type": "normal",
            "title": "T",
            "desc": "",
            "video_urls": [],
            "time": "",
            "last_update_time": "",
            "ip_location": "",
            "image_list": [],
            "tag_list": [],
            "url": f"{XHS_WEB_URL}/explore/{note_id}?xsec_token=&xsec_source=pc_search",
            "note_url": f"{XHS_WEB_URL}/explore/{note_id}?xsec_token=&xsec_source=pc_search",
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "user": {"user_id": "", "nickname": "", "avatar": ""},
        }

    @pytest.mark.asyncio
    async def test_api_success(self):
        adapter = self._make_adapter()
        note = self._make_normalized_note()
        adapter._fetch_note_by_api = AsyncMock(return_value=note)
        adapter._fetch_note_by_html = AsyncMock()

        url = f"{XHS_WEB_URL}/explore/n1?xsec_token=tok&xsec_source=src"
        result = await adapter.fetch_post(note_url=url)
        assert result["note"]["note_id"] == "n1"
        assert result["platform"] == "xhs"
        assert result["comments"] == []
        adapter._fetch_note_by_html.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_api_fails_html_fallback(self):
        adapter = self._make_adapter()
        note = self._make_normalized_note()
        adapter._fetch_note_by_api = AsyncMock(side_effect=Exception("API error"))
        adapter._fetch_note_by_html = AsyncMock(return_value=note)

        url = f"{XHS_WEB_URL}/explore/n1?xsec_token=tok&xsec_source=src"
        result = await adapter.fetch_post(note_url=url)
        assert result["note"]["note_id"] == "n1"

    @pytest.mark.asyncio
    async def test_api_returns_none_html_fallback(self):
        adapter = self._make_adapter()
        note = self._make_normalized_note()
        adapter._fetch_note_by_api = AsyncMock(return_value=None)
        adapter._fetch_note_by_html = AsyncMock(return_value=note)

        url = f"{XHS_WEB_URL}/explore/n1"
        result = await adapter.fetch_post(note_url=url)
        assert result["note"]["note_id"] == "n1"

    @pytest.mark.asyncio
    async def test_both_fail_raises(self):
        adapter = self._make_adapter()
        adapter._fetch_note_by_api = AsyncMock(return_value=None)
        adapter._fetch_note_by_html = AsyncMock(return_value=None)

        url = f"{XHS_WEB_URL}/explore/n1"
        with pytest.raises(ScraperError, match="Cannot fetch note"):
            await adapter.fetch_post(note_url=url)

    @pytest.mark.asyncio
    async def test_short_url_triggers_redirect(self):
        adapter = self._make_adapter()
        note = self._make_normalized_note()
        adapter._get_redirection_url = AsyncMock(
            return_value=f"{XHS_WEB_URL}/explore/n1?xsec_token=tok&xsec_source=src"
        )
        adapter._fetch_note_by_api = AsyncMock(return_value=note)

        result = await adapter.fetch_post(note_url="https://xhslink.com/abc")
        adapter._get_redirection_url.assert_awaited_once()
        assert result["note"]["note_id"] == "n1"

    @pytest.mark.asyncio
    async def test_with_comments(self):
        adapter = self._make_adapter()
        note = self._make_normalized_note()
        adapter._fetch_note_by_api = AsyncMock(return_value=note)
        adapter._fetch_comments = AsyncMock(return_value=[{"comment_id": "c1"}])

        url = f"{XHS_WEB_URL}/explore/n1"
        result = await adapter.fetch_post(note_url=url, with_comments=True, max_comments=10)
        assert len(result["comments"]) == 1

    @pytest.mark.asyncio
    async def test_with_comments_error_returns_empty(self):
        adapter = self._make_adapter()
        note = self._make_normalized_note()
        adapter._fetch_note_by_api = AsyncMock(return_value=note)
        adapter._fetch_comments = AsyncMock(side_effect=Exception("comment error"))

        url = f"{XHS_WEB_URL}/explore/n1"
        result = await adapter.fetch_post(note_url=url, with_comments=True)
        assert result["comments"] == []

    @pytest.mark.asyncio
    async def test_url_in_result_is_pure(self):
        adapter = self._make_adapter()
        note = self._make_normalized_note()
        adapter._fetch_note_by_api = AsyncMock(return_value=note)

        url = f"{XHS_WEB_URL}/explore/n1?xsec_token=tok&xsec_source=src"
        result = await adapter.fetch_post(note_url=url)
        assert result["url"] == f"{XHS_WEB_URL}/explore/n1"


class TestFetchComments:
    """Tests for _fetch_comments."""

    def _make_adapter(self):
        return XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )

    @pytest.mark.asyncio
    async def test_single_page(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [
                {"id": "c1", "content": "hi", "user_info": {}, "target_comment": {}, "pictures": []},
            ],
            "has_more": False,
            "cursor": "",
        })
        result = await adapter._fetch_comments("n1", "tok")
        assert len(result) == 1
        assert result[0]["comment_id"] == "c1"

    @pytest.mark.asyncio
    async def test_pagination(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(side_effect=[
            {
                "comments": [{"id": "c1", "content": "a", "user_info": {}, "target_comment": {}, "pictures": []}],
                "has_more": True,
                "cursor": "page2",
            },
            {
                "comments": [{"id": "c2", "content": "b", "user_info": {}, "target_comment": {}, "pictures": []}],
                "has_more": False,
                "cursor": "",
            },
        ])
        result = await adapter._fetch_comments("n1", "tok")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_max_comments(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [
                {"id": f"c{i}", "content": str(i), "user_info": {}, "target_comment": {}, "pictures": []}
                for i in range(5)
            ],
            "has_more": True,
            "cursor": "next",
        })
        result = await adapter._fetch_comments("n1", "tok", max_comments=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_no_cursor_breaks_loop(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [{"id": "c1", "content": "a", "user_info": {}, "target_comment": {}, "pictures": []}],
            "has_more": True,
            "cursor": "",
        })
        result = await adapter._fetch_comments("n1", "tok")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_with_xsec_token_in_params(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [],
            "has_more": False,
            "cursor": "",
        })
        await adapter._fetch_comments("n1", "tok")
        call_params = adapter._signed_get.call_args.kwargs.get("params") or adapter._signed_get.call_args[1].get("params")
        assert call_params["xsec_token"] == "tok"

    @pytest.mark.asyncio
    async def test_without_xsec_token(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [],
            "has_more": False,
            "cursor": "",
        })
        await adapter._fetch_comments("n1", "")
        call_params = adapter._signed_get.call_args.kwargs.get("params") or adapter._signed_get.call_args[1].get("params")
        assert "xsec_token" not in call_params

    @pytest.mark.asyncio
    async def test_none_comments_treated_as_empty(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": None,
            "has_more": False,
            "cursor": "",
        })
        result = await adapter._fetch_comments("n1", "tok")
        assert result == []

    @pytest.mark.asyncio
    async def test_include_sub_comments(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [
                {
                    "id": "c1", "content": "root", "user_info": {}, "target_comment": {},
                    "pictures": [], "sub_comments": [
                        {"id": "sc1", "content": "sub", "user_info": {}, "target_comment": {}, "pictures": []},
                    ],
                    "sub_comment_has_more": False,
                    "sub_comment_cursor": "",
                },
            ],
            "has_more": False,
            "cursor": "",
        })
        adapter._fetch_sub_comments = AsyncMock(return_value=[
            {"comment_id": "sc1", "content": "sub"},
        ])
        result = await adapter._fetch_comments("n1", "tok", include_sub_comments=True)
        assert len(result) == 2
        adapter._fetch_sub_comments.assert_awaited_once()


class TestFetchSubComments:
    """Tests for _fetch_sub_comments."""

    def _make_adapter(self):
        return XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )

    @pytest.mark.asyncio
    async def test_inline_only(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock()  # should not be called
        root = {
            "id": "c1",
            "sub_comments": [
                {"id": "sc1", "content": "inline", "user_info": {}, "target_comment": {}, "pictures": []},
            ],
            "sub_comment_has_more": False,
            "sub_comment_cursor": "",
        }
        result = await adapter._fetch_sub_comments("n1", root, "tok")
        assert len(result) == 1
        assert result[0]["comment_id"] == "sc1"
        adapter._signed_get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pagination(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(side_effect=[
            {
                "comments": [{"id": "sc2", "content": "p1", "user_info": {}, "target_comment": {}, "pictures": []}],
                "has_more": True,
                "cursor": "next_cursor",
            },
            {
                "comments": [{"id": "sc3", "content": "p2", "user_info": {}, "target_comment": {}, "pictures": []}],
                "has_more": False,
                "cursor": "",
            },
        ])
        root = {
            "id": "c1",
            "sub_comments": [],
            "sub_comment_has_more": True,
            "sub_comment_cursor": "first_cursor",
        }
        result = await adapter._fetch_sub_comments("n1", root, "tok")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_no_cursor_breaks(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [{"id": "sc1", "content": "x", "user_info": {}, "target_comment": {}, "pictures": []}],
            "has_more": True,
            "cursor": "",
        })
        root = {
            "id": "c1",
            "sub_comments": [],
            "sub_comment_has_more": True,
            "sub_comment_cursor": "start",
        }
        result = await adapter._fetch_sub_comments("n1", root, "tok")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_none_sub_comments(self):
        adapter = self._make_adapter()
        root = {
            "id": "c1",
            "sub_comments": None,
            "sub_comment_has_more": False,
        }
        result = await adapter._fetch_sub_comments("n1", root, "")
        assert result == []

    @pytest.mark.asyncio
    async def test_xsec_token_in_params(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [],
            "has_more": False,
            "cursor": "",
        })
        root = {
            "id": "c1",
            "sub_comments": [],
            "sub_comment_has_more": True,
            "sub_comment_cursor": "cur",
        }
        await adapter._fetch_sub_comments("n1", root, "my_tok")
        call_params = adapter._signed_get.call_args.kwargs.get("params") or adapter._signed_get.call_args[1].get("params")
        assert call_params["xsec_token"] == "my_tok"

    @pytest.mark.asyncio
    async def test_no_xsec_token_in_params(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": [],
            "has_more": False,
            "cursor": "",
        })
        root = {
            "id": "c1",
            "sub_comments": [],
            "sub_comment_has_more": True,
            "sub_comment_cursor": "cur",
        }
        await adapter._fetch_sub_comments("n1", root, "")
        call_params = adapter._signed_get.call_args.kwargs.get("params") or adapter._signed_get.call_args[1].get("params")
        assert "xsec_token" not in call_params

    @pytest.mark.asyncio
    async def test_none_sub_comments_list_in_payload(self):
        adapter = self._make_adapter()
        adapter._signed_get = AsyncMock(return_value={
            "comments": None,
            "has_more": False,
            "cursor": "",
        })
        root = {
            "id": "c1",
            "sub_comments": [],
            "sub_comment_has_more": True,
            "sub_comment_cursor": "cur",
        }
        result = await adapter._fetch_sub_comments("n1", root, "")
        assert result == []


class TestGetRedirectionUrl:
    """Tests for _get_redirection_url."""

    @pytest.mark.asyncio
    async def test_success(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        mock_resp = MagicMock()
        mock_resp.url = "https://www.xiaohongshu.com/explore/n1?xsec_token=tok"

        with patch("fastfetchbot_shared.services.scrapers.xiaohongshu.adaptar.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            result = await adapter._get_redirection_url("https://xhslink.com/abc")
            assert "xiaohongshu.com" in result

    @pytest.mark.asyncio
    async def test_not_xhs_raises(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        mock_resp = MagicMock()
        mock_resp.url = "https://www.google.com/"

        with patch("fastfetchbot_shared.services.scrapers.xiaohongshu.adaptar.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            with pytest.raises(ScraperError, match="did not redirect to xiaohongshu.com"):
                await adapter._get_redirection_url("https://xhslink.com/abc")


class TestSignedPost:
    """Tests for _signed_post."""

    @pytest.mark.asyncio
    async def test_signed_post(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        adapter._sign_headers = AsyncMock(return_value={"X-s": "val"})
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": {"result": "ok"}}
        adapter._http = AsyncMock()
        adapter._http.post = AsyncMock(return_value=mock_resp)

        result = await adapter._signed_post("/api/test", data={"key": "val"})
        assert result == {"result": "ok"}
        adapter._sign_headers.assert_awaited_once()


class TestSignedGet:
    """Tests for _signed_get."""

    @pytest.mark.asyncio
    async def test_signed_get_with_params(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        adapter._sign_headers = AsyncMock(return_value={"X-s": "val"})
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": {"items": []}}
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        result = await adapter._signed_get("/api/test", params={"a": "1"})
        assert result == {"items": []}
        # Verify the sign_headers was called with URI including query string
        sign_uri = adapter._sign_headers.call_args.kwargs.get("uri") or adapter._sign_headers.call_args[1].get("uri")
        assert "a=1" in sign_uri

    @pytest.mark.asyncio
    async def test_signed_get_no_params(self):
        adapter = XhsSinglePostAdapter(
            cookies="c=1", sign_server_endpoint="http://s:8989"
        )
        adapter._sign_headers = AsyncMock(return_value={"X-s": "val"})
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": {"items": []}}
        adapter._http = AsyncMock()
        adapter._http.get = AsyncMock(return_value=mock_resp)

        await adapter._signed_get("/api/test")
        sign_uri = adapter._sign_headers.call_args.kwargs.get("uri") or adapter._sign_headers.call_args[1].get("uri")
        assert sign_uri == "/api/test"


# ---------------------------------------------------------------------------
# Xiaohongshu class tests (from __init__.py)
# ---------------------------------------------------------------------------

class TestXiaohongshuInit:
    """Tests for Xiaohongshu.__init__."""

    @patch("fastfetchbot_shared.services.scrapers.xiaohongshu.JINJA2_ENV")
    def test_init(self, mock_env):
        mock_template = MagicMock()
        mock_template.render.return_value = "<p>rendered</p>"
        mock_env.get_template.return_value = mock_template

        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu
        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n1", data=None)
        assert xhs.url == "https://www.xiaohongshu.com/explore/n1"
        assert xhs.category == "xiaohongshu"
        assert xhs.message_type == MessageType.SHORT
        assert xhs.media_files == []
        assert xhs.id is None


class TestXiaohongshuGetItem:
    """Tests for Xiaohongshu.get_item and _get_xiaohongshu."""

    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n1", data=None)
        note = {
            "note_id": "n1",
            "title": "Test Note",
            "desc": "Description",
            "user": {"user_id": "u1", "nickname": "Nick", "avatar": ""},
            "time": 1700000000000,
            "last_update_time": 1700001000000,
            "liked_count": 10,
            "collected_count": 5,
            "comment_count": 3,
            "share_count": 2,
            "ip_location": "Beijing",
            "image_list": ["https://img1.jpg"],
            "video_urls": [],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note,
            "url": "https://www.xiaohongshu.com/explore/n1",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ):
            result = await xhs.get_item()

        assert isinstance(result, dict)
        assert result["category"] == "xiaohongshu"
        assert xhs.id == "n1"

    @pytest.mark.asyncio
    async def test_get_item_with_video(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n2", data=None)
        note = {
            "note_id": "n2",
            "title": "Video Note",
            "desc": "Vid desc",
            "user": {"user_id": "u1", "nickname": "Nick", "avatar": ""},
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": [],
            "video_urls": ["https://video.mp4"],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note,
            "url": "https://www.xiaohongshu.com/explore/n2",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ):
            result = await xhs.get_item()

        video_files = [mf for mf in xhs.media_files if mf.media_type == "video"]
        assert len(video_files) == 1

    @pytest.mark.asyncio
    async def test_no_title_uses_author_fallback(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n3", data=None)
        note = {
            "note_id": "n3",
            "title": "",
            "desc": "desc",
            "user": {"user_id": "u1", "nickname": "Author", "avatar": ""},
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": [],
            "video_urls": [],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note, "url": "https://www.xiaohongshu.com/explore/n3",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ):
            await xhs.get_item()

        assert xhs.title == "Author\u7684\u5c0f\u7ea2\u4e66\u7b14\u8bb0"

    @pytest.mark.asyncio
    async def test_no_title_no_author(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n4", data=None)
        note = {
            "note_id": "n4",
            "title": "",
            "desc": "",
            "user": {"user_id": "u1", "nickname": "", "avatar": ""},
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": [],
            "video_urls": [],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note, "url": "https://www.xiaohongshu.com/explore/n4",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ):
            await xhs.get_item()

        # title stays empty/falsy, fallback condition is not met since author is also falsy
        assert not xhs.title

    @pytest.mark.asyncio
    async def test_long_text_switches_message_type(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        # Make the template render a long string
        mock_jinja2_env.get_template.return_value.render.return_value = "a" * 600

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n5", data=None)
        note = {
            "note_id": "n5",
            "title": "Long",
            "desc": "x" * 600,
            "user": {"user_id": "u1", "nickname": "N", "avatar": ""},
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": [],
            "video_urls": [],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note, "url": "https://www.xiaohongshu.com/explore/n5",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ):
            await xhs.get_item()

        assert xhs.message_type == MessageType.LONG

    @pytest.mark.asyncio
    async def test_raw_content_tab_and_newline_stripping(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        mock_short_template = MagicMock()
        mock_short_template.render.return_value = "<p>short</p>"
        mock_content_template = MagicMock()
        mock_content_template.render.return_value = "<p>content</p>"

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n6", data=None)
        note = {
            "note_id": "n6",
            "title": "Tabs",
            "desc": "line1\t\tline2\n",
            "user": {"user_id": "u1", "nickname": "N", "avatar": ""},
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": [],
            "video_urls": [],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note, "url": "https://www.xiaohongshu.com/explore/n6",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ), patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.short_text_template",
            mock_short_template,
        ), patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.content_template",
            mock_content_template,
        ):
            await xhs.get_item()

        # raw_content should have tabs stripped and trailing newline removed
        render_calls = mock_short_template.render.call_args_list
        first_call_data = render_calls[0].kwargs.get("data") or render_calls[0][1].get("data")
        assert "\t" not in first_call_data["raw_content"]

    @pytest.mark.asyncio
    async def test_none_user(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n7", data=None)
        note = {
            "note_id": "n7",
            "title": "No User",
            "desc": "",
            "user": None,
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": None,
            "video_urls": None,
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note, "url": "https://www.xiaohongshu.com/explore/n7",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ):
            result = await xhs.get_item()

        assert result is not None

    @pytest.mark.asyncio
    async def test_none_raw_content(self, mock_jinja2_env):
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n8", data=None)
        note = {
            "note_id": "n8",
            "title": "No Desc",
            "desc": None,
            "user": {"user_id": "u1", "nickname": "N", "avatar": ""},
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": [],
            "video_urls": [],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note, "url": "https://www.xiaohongshu.com/explore/n8",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ):
            await xhs.get_item()

        # raw_content should be empty string, not None
        assert xhs.raw_content is None or xhs.raw_content == ""

    @pytest.mark.asyncio
    async def test_content_template_includes_media(self, mock_jinja2_env):
        """Verify that content template render is called after media files are appended."""
        from fastfetchbot_shared.services.scrapers.xiaohongshu import Xiaohongshu

        mock_short_template = MagicMock()
        mock_short_template.render.return_value = "<p>short</p>"
        mock_content_template = MagicMock()
        mock_content_template.render.return_value = "<p>content</p>"

        xhs = Xiaohongshu(url="https://www.xiaohongshu.com/explore/n9", data=None)
        note = {
            "note_id": "n9",
            "title": "Media",
            "desc": "desc",
            "user": {"user_id": "u1", "nickname": "N", "avatar": ""},
            "time": 0,
            "last_update_time": 0,
            "liked_count": 0,
            "collected_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "ip_location": "",
            "image_list": ["https://img.jpg"],
            "video_urls": ["https://vid.mp4"],
        }

        mock_adapter = AsyncMock()
        mock_adapter.fetch_post = AsyncMock(return_value={
            "note": note, "url": "https://www.xiaohongshu.com/explore/n9",
        })
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.XhsSinglePostAdapter",
            return_value=mock_adapter,
        ), patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.short_text_template",
            mock_short_template,
        ), patch(
            "fastfetchbot_shared.services.scrapers.xiaohongshu.content_template",
            mock_content_template,
        ):
            await xhs.get_item()

        # content_template.render was called
        render_calls = mock_content_template.render.call_args_list
        assert len(render_calls) == 1
        call_data = render_calls[0].kwargs.get("data") or render_calls[0][1].get("data")
        # raw_content should have img and video tags appended
        assert "img" in call_data["raw_content"]
        assert "video" in call_data["raw_content"]

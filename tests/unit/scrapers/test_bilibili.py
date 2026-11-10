"""Tests for fastfetchbot_shared.services.scrapers.bilibili (URL resolver + view API)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fastfetchbot_shared.exceptions import ScraperError
from fastfetchbot_shared.services.scrapers.bilibili import (
    BilibiliApiUnavailable,
    extract_video_id,
    fetch_bilibili_video_meta,
    resolve_bilibili_url,
)

BV = "BV1xx411c7mD"
URL_CLIENT = "fastfetchbot_shared.services.scrapers.bilibili.url.httpx.AsyncClient"
API_CLIENT = "fastfetchbot_shared.services.scrapers.bilibili.api.httpx.AsyncClient"


def _client(response=None, side_effect=None):
    client = AsyncMock()
    client.get = AsyncMock(return_value=response, side_effect=side_effect)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _redirect(final_url: str):
    resp = MagicMock()
    resp.url = httpx.URL(final_url)
    return _client(resp)


# ---------------------------------------------------------------------------
# resolve_bilibili_url
# ---------------------------------------------------------------------------


class TestResolveBilibiliUrl:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (f"https://www.bilibili.com/video/{BV}", f"https://www.bilibili.com/video/{BV}"),
            (f"https://www.bilibili.com/video/{BV}/?spm_id_from=333&vd_source=x",
             f"https://www.bilibili.com/video/{BV}"),
            (f"https://m.bilibili.com/video/{BV}", f"https://www.bilibili.com/video/{BV}"),
            (f"bilibili.com/video/{BV}", f"https://www.bilibili.com/video/{BV}"),
            (f"https://www.bilibili.com/video/{BV}?p=1", f"https://www.bilibili.com/video/{BV}"),
            (f"https://www.bilibili.com/video/{BV}?p=2&t=10", f"https://www.bilibili.com/video/{BV}?p=2"),
            ("https://www.bilibili.com/video/AV170001", "https://www.bilibili.com/video/av170001"),
        ],
    )
    async def test_normalizes_direct_links(self, raw, expected):
        assert await resolve_bilibili_url(raw) == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("short", ["https://b23.tv/abc123", "https://bili2233.cn/abc123"])
    async def test_expands_short_links_and_rechecks_host(self, short):
        client = _redirect(f"https://m.bilibili.com/video/{BV}?share_source=copy_web&p=3")
        with patch(URL_CLIENT, return_value=client) as cls:
            result = await resolve_bilibili_url(short)
        assert result == f"https://www.bilibili.com/video/{BV}?p=3"
        assert cls.call_args.kwargs["follow_redirects"] is True

    @pytest.mark.asyncio
    async def test_short_link_network_error(self):
        client = _client(side_effect=httpx.ConnectTimeout("t"))
        with patch(URL_CLIENT, return_value=client):
            with pytest.raises(ScraperError, match="短链展开失败"):
                await resolve_bilibili_url("https://b23.tv/abc")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "final, reason",
        [
            ("https://www.bilibili.com/bangumi/play/ep123", "番剧"),
            ("https://live.bilibili.com/123", "直播"),
            ("https://mall.bilibili.com/detail.html?itemsId=1", "商品"),
            ("https://www.bilibili.com/", "短链可能已失效"),
            ("https://space.bilibili.com/123", "短链可能已失效"),
        ],
    )
    async def test_rejects_non_video_targets(self, final, reason):
        with patch(URL_CLIENT, return_value=_redirect(final)):
            with pytest.raises(ScraperError, match=reason):
                await resolve_bilibili_url("https://b23.tv/abc")


class TestExtractVideoId:
    def test_bvid(self):
        assert extract_video_id(f"https://www.bilibili.com/video/{BV}") == {"bvid": BV, "p": 1}

    def test_aid_with_page(self):
        assert extract_video_id("https://www.bilibili.com/video/av170001?p=2") == {"aid": "170001", "p": 2}

    def test_invalid(self):
        with pytest.raises(ScraperError):
            extract_video_id("https://www.bilibili.com/read/cv1")


# ---------------------------------------------------------------------------
# fetch_bilibili_video_meta
# ---------------------------------------------------------------------------


def _view_response(payload=None, status=200, json_error=False):
    resp = MagicMock()
    resp.status_code = status
    if json_error:
        resp.json.side_effect = ValueError("bad json")
    else:
        resp.json.return_value = payload
    return resp


VIEW_DATA = {
    "bvid": BV,
    "title": "标题",
    "desc": "简介",
    "pic": "https://i0.hdslb.com/pic.jpg",
    "pubdate": 1704067200,
    "duration": 600,
    "owner": {"mid": 42, "name": "UP主"},
    "stat": {"view": 100, "danmaku": 20, "reply": 5, "like": 30},
    "pages": [
        {"page": 1, "cid": 1, "duration": 200},
        {"page": 2, "cid": 2, "duration": 400},
    ],
}


class TestFetchBilibiliVideoMeta:
    @pytest.mark.asyncio
    async def test_maps_view_payload(self):
        client = _client(_view_response({"code": 0, "data": VIEW_DATA}))
        with patch(API_CLIENT, return_value=client):
            meta = await fetch_bilibili_video_meta(f"https://www.bilibili.com/video/{BV}")
        client.get.assert_awaited_once()
        assert client.get.call_args.kwargs["params"] == {"bvid": BV}
        assert meta["id"] == BV
        assert meta["title"] == "标题"
        assert meta["author"] == "UP主"
        assert meta["author_url"] == "https://space.bilibili.com/42"
        assert meta["description"] == "简介"
        assert meta["playback_data"] == "视频播放量：100 弹幕数：20 点赞数：30"
        assert meta["timestamp"] == 1704067200
        assert meta["upload_date"]
        assert meta["duration"] == "00:03:20"  # page 1

    @pytest.mark.asyncio
    async def test_page_duration_and_aid_param(self):
        client = _client(_view_response({"code": 0, "data": VIEW_DATA}))
        with patch(API_CLIENT, return_value=client):
            meta = await fetch_bilibili_video_meta("https://www.bilibili.com/video/av170001?p=2")
        assert client.get.call_args.kwargs["params"] == {"aid": "170001"}
        assert meta["duration"] == "00:06:40"

    @pytest.mark.asyncio
    async def test_out_of_range_page_uses_total_duration(self):
        client = _client(_view_response({"code": 0, "data": VIEW_DATA}))
        with patch(API_CLIENT, return_value=client):
            meta = await fetch_bilibili_video_meta(f"https://www.bilibili.com/video/{BV}?p=9")
        assert meta["duration"] == "00:10:00"

    @pytest.mark.asyncio
    async def test_dash_description_is_empty(self):
        data = {**VIEW_DATA, "desc": "-"}
        with patch(API_CLIENT, return_value=_client(_view_response({"code": 0, "data": data}))):
            meta = await fetch_bilibili_video_meta(f"https://www.bilibili.com/video/{BV}")
        assert meta["description"] == ""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "code, reason",
        [(-404, "不存在"), (62002, "不可见"), (62004, "审核中"), (62012, "仅 UP 主")],
    )
    async def test_fatal_codes_raise_scraper_error(self, code, reason):
        with patch(API_CLIENT, return_value=_client(_view_response({"code": code, "message": "x"}))):
            with pytest.raises(ScraperError, match=reason) as exc_info:
                await fetch_bilibili_video_meta(f"https://www.bilibili.com/video/{BV}")
        assert not isinstance(exc_info.value, BilibiliApiUnavailable)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response, side_effect",
        [
            (_view_response(status=412), None),
            (_view_response(status=500), None),
            (_view_response({"code": -352, "message": "风控校验失败"}), None),
            (_view_response({"code": -403, "message": "访问权限不足"}), None),
            (_view_response(json_error=True), None),
            (_view_response([]), None),
            (_view_response(None), None),
            (_view_response("ok"), None),
            (_view_response({"code": 0, "data": {"title": "missing fields"}}), None),
            (None, httpx.ConnectError("boom")),
        ],
    )
    async def test_retryable_failures_raise_unavailable(self, response, side_effect):
        with patch(API_CLIENT, return_value=_client(response, side_effect)):
            with pytest.raises(BilibiliApiUnavailable):
                await fetch_bilibili_video_meta(f"https://www.bilibili.com/video/{BV}")

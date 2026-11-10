"""Tests for Bilibili dynamics/opus: parsing, fetching, the MetadataItem, and URL routing."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from fastfetchbot_shared.exceptions import ScraperError
from fastfetchbot_shared.models.metadata_item import MessageType
from fastfetchbot_shared.services.scrapers.bilibili import BilibiliStatus
from fastfetchbot_shared.services.scrapers.bilibili import dynamic as dyn_mod
from fastfetchbot_shared.services.scrapers.bilibili.dynamic import (
    clean_bilibili_hashtags,
    fetch_dynamic_item,
    parse_dynamic_item,
)
from fastfetchbot_shared.utils import bilibili as bili_utils
from fastfetchbot_shared.utils.parse import get_url_metadata

DYN_ID = "1169207844562534435"
ORIG_ID = "1169207844562534000"
_RealAsyncClient = httpx.AsyncClient


def _item(module_dynamic, *, id_str=DYN_ID, type_="DYNAMIC_TYPE_DRAW", orig=None, author="UP主", mid=42):
    item = {
        "id_str": id_str,
        "type": type_,
        "modules": {
            "module_author": {"name": author, "mid": mid, "pub_ts": 1704067200},
            "module_dynamic": module_dynamic,
            "module_stat": {"comment": {"count": 3}, "forward": {"count": 4}, "like": {"count": 5}},
        },
    }
    if orig is not None:
        item["orig"] = orig
    return item


OPUS_ITEM = _item({
    "desc": None,
    "major": {
        "type": "MAJOR_TYPE_OPUS",
        "opus": {
            "title": "图文标题",
            "summary": {"text": "正文 #话题#内容"},
            "pics": [
                {"url": "http://i0.hdslb.com/a.jpg", "width": 1080, "height": 1440, "live_url": None},
                {"url": "https://i0.hdslb.com/b.jpg", "width": 800, "height": 600,
                 "live_url": "//upos.bilivideo.com/live.mp4"},
            ],
        },
    },
})

ARCHIVE_ITEM = _item({
    "desc": {"text": "投稿了新视频"},
    "major": {
        "type": "MAJOR_TYPE_ARCHIVE",
        "archive": {"title": "视频标题", "desc": "视频简介", "cover": "//i0.hdslb.com/cover.jpg",
                    "jump_url": "//www.bilibili.com/video/BV1xx411c7mD/", "bvid": "BV1xx411c7mD"},
    },
}, type_="DYNAMIC_TYPE_AV")

FORWARD_ITEM = _item(
    {"desc": {"text": "转发评论"}, "major": None},
    type_="DYNAMIC_TYPE_FORWARD",
    orig=_item(OPUS_ITEM["modules"]["module_dynamic"], id_str=ORIG_ID, author="原作者", mid=7),
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class TestCleanHashtags:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("前文#话题#后文", "前文 #话题 后文"),
            ("#a##b# 尾巴", "#a #b 尾巴"),
            ("没有话题", "没有话题"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_cleans(self, raw, expected):
        assert clean_bilibili_hashtags(raw) == expected


class TestParseDynamicItem:
    def test_opus(self):
        d = parse_dynamic_item(OPUS_ITEM)
        assert d["id"] == DYN_ID
        assert d["author"] == "UP主" and d["author_mid"] == 42
        assert d["timestamp"] == 1704067200
        assert d["title"] == "图文标题"
        assert d["text"] == "正文 #话题 内容"
        assert d["stats"] == {"comment": 3, "forward": 4, "like": 5}
        assert d["images"][0] == {"url": "https://i0.hdslb.com/a.jpg", "width": 1080, "height": 1440, "live_url": None}
        assert d["images"][1]["live_url"] == "https://upos.bilivideo.com/live.mp4"
        assert d["orig"] is None

    def test_archive_prefers_desc_and_keeps_link_and_cover(self):
        d = parse_dynamic_item(ARCHIVE_ITEM)
        assert d["title"] == "视频标题"
        assert d["text"] == "投稿了新视频"
        assert d["link"] == "https://www.bilibili.com/video/BV1xx411c7mD/"
        assert d["images"][0]["url"] == "https://i0.hdslb.com/cover.jpg"

    def test_archive_without_desc_uses_video_desc(self):
        item = _item({**ARCHIVE_ITEM["modules"]["module_dynamic"], "desc": None})
        assert parse_dynamic_item(item)["text"] == "视频简介"

    def test_forward_parses_orig(self):
        d = parse_dynamic_item(FORWARD_ITEM)
        assert d["text"] == "转发评论"
        assert d["images"] == []
        assert d["orig"]["id"] == ORIG_ID
        assert d["orig"]["author"] == "原作者"
        assert len(d["orig"]["images"]) == 2

    def test_word_dynamic(self):
        d = parse_dynamic_item(_item({"desc": {"text": "纯文字"}, "major": None}, type_="DYNAMIC_TYPE_WORD"))
        assert (d["title"], d["text"], d["images"], d["link"]) == ("", "纯文字", [], None)

    def test_live_and_upower(self):
        live = parse_dynamic_item(_item({"desc": None, "major": {"type": "MAJOR_TYPE_LIVE", "live": {
            "title": "直播间", "desc_first": "游戏", "desc_second": "100人看过", "cover": "https://i0.hdslb.com/l.jpg",
            "jump_url": "//live.bilibili.com/1"}}}))
        assert live["text"] == "游戏 · 100人看过"
        assert live["link"] == "https://live.bilibili.com/1"
        upower = parse_dynamic_item(_item({"desc": None, "major": {"type": "MAJOR_TYPE_UPOWER_COMMON",
                                                                    "upower_common": {"title_prefix": "充电专属", "title": "标题"}}}))
        assert upower["title"] == "充电专属: 标题"

    def test_unknown_major_keeps_desc(self):
        d = parse_dynamic_item(_item({"desc": {"text": "文字"}, "major": {"type": "MAJOR_TYPE_NEW_THING"}}))
        assert d["text"] == "文字" and d["images"] == []


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


class FakeApi:
    def __init__(self, detail=None, status=200, spi_ok=True):
        self.detail = detail if detail is not None else {"code": 0, "data": {"item": OPUS_ITEM}}
        self.status = status
        self.spi_ok = spi_ok
        self.requests: list[httpx.Request] = []

    def handler(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/finger/spi"):
            if not self.spi_ok:
                return httpx.Response(500)
            return httpx.Response(200, json={"code": 0, "data": {"b_3": "B3", "b_4": "B4"}})
        if self.status != 200:
            return httpx.Response(self.status)
        if self.detail == "not-json":
            return httpx.Response(200, content=b"<html>")
        return httpx.Response(200, json=self.detail)

    async def fetch(self):
        transport = httpx.MockTransport(self.handler)
        with patch.object(dyn_mod.httpx, "AsyncClient", lambda **kw: _RealAsyncClient(transport=transport, **kw)):
            return await fetch_dynamic_item(DYN_ID)


class TestFetchDynamicItem:
    @pytest.mark.asyncio
    async def test_success_sends_guest_cookies_and_params(self):
        api = FakeApi()
        item = await api.fetch()
        assert item["id_str"] == DYN_ID
        detail = api.requests[-1]
        assert detail.url.params["id"] == DYN_ID
        assert detail.url.params["features"] == "itemOpusStyle"
        assert "buvid3=B3" in detail.headers["cookie"]
        assert detail.headers["referer"] == f"https://t.bilibili.com/{DYN_ID}"

    @pytest.mark.asyncio
    async def test_spi_failure_is_not_fatal(self):
        assert (await FakeApi(spi_ok=False).fetch())["id_str"] == DYN_ID

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "api, reason",
        [
            (FakeApi(status=412), "风控拦截"),
            (FakeApi(status=500), "HTTP 500"),
            (FakeApi(detail={"code": -352, "message": "x"}), "风控拦截"),
            (FakeApi(detail={"code": 4101152, "message": "x"}), "动态不可见"),
            (FakeApi(detail={"code": 4101131, "message": "内容不存在"}), "内容不存在"),
            (FakeApi(detail={"code": 0, "data": {}}), "未知错误"),
            (FakeApi(detail="not-json"), "不是 JSON"),
            (FakeApi(detail=[]), "数据结构异常"),
            (FakeApi(detail={"code": 0, "data": ["x"]}), "未知错误"),
        ],
    )
    async def test_errors(self, api, reason):
        with pytest.raises(ScraperError, match=reason):
            await api.fetch()

    @pytest.mark.asyncio
    async def test_network_error(self):
        def boom(request):
            raise httpx.ConnectError("x")

        transport = httpx.MockTransport(boom)
        with patch.object(dyn_mod.httpx, "AsyncClient", lambda **kw: _RealAsyncClient(transport=transport, **kw)):
            with pytest.raises(ScraperError, match="ConnectError"):
                await fetch_dynamic_item(DYN_ID)


# ---------------------------------------------------------------------------
# BilibiliStatus MetadataItem
# ---------------------------------------------------------------------------

FETCH_PATCH = "fastfetchbot_shared.services.scrapers.bilibili.item.fetch_dynamic_item"


class TestBilibiliStatusItem:
    @pytest.mark.asyncio
    async def test_opus_item(self):
        with patch(FETCH_PATCH, AsyncMock(return_value=OPUS_ITEM)) as fetch:
            result = await BilibiliStatus(url=f"https://www.bilibili.com/opus/{DYN_ID}").get_item()
        fetch.assert_awaited_once_with(DYN_ID)
        assert result["category"] == "bilibili_status"
        assert result["url"] == f"https://t.bilibili.com/{DYN_ID}"
        assert result["title"] == "图文标题"
        assert result["author"] == "UP主"
        assert result["author_url"] == "https://space.bilibili.com/42"
        assert result["message_type"] == MessageType.SHORT
        kinds = [m["media_type"] for m in result["media_files"]]
        assert kinds == ["image", "image", "video"]  # live photo -> still + motion
        assert "正文 #话题 内容" in result["text"]
        assert "转发：4 评论：3 点赞：5" in result["content"]

    @pytest.mark.asyncio
    async def test_forward_item_quotes_orig_and_includes_its_media(self):
        with patch(FETCH_PATCH, AsyncMock(return_value=FORWARD_ITEM)):
            result = await BilibiliStatus(url=f"https://t.bilibili.com/{DYN_ID}").get_item()
        assert result["title"] == "UP主的B站动态"
        assert "// @原作者：图文标题" in result["text"]
        assert "<blockquote>" in result["content"]
        assert "https://space.bilibili.com/7" in result["content"]
        assert len(result["media_files"]) == 3

    @pytest.mark.asyncio
    async def test_archive_item_links_video(self):
        with patch(FETCH_PATCH, AsyncMock(return_value=ARCHIVE_ITEM)):
            result = await BilibiliStatus(url=f"https://t.bilibili.com/{DYN_ID}").get_item()
        assert "https://www.bilibili.com/video/BV1xx411c7mD/" in result["text"]
        assert result["media_files"][0]["url"] == "https://i0.hdslb.com/cover.jpg"

    @pytest.mark.asyncio
    async def test_user_text_is_html_escaped(self):
        evil_orig = _item({"desc": None, "major": {"type": "MAJOR_TYPE_ARCHIVE", "archive": {
            "title": "<i>原标题</i>", "desc": "x > y", "cover": "",
            "jump_url": 'https://www.bilibili.com/video/BV1"onclick="a', "bvid": "BV1xx411c7mD"}}},
            id_str=ORIG_ID, author="<u>原作者</u>", mid=7)
        evil = _item({"desc": {"text": "a < b <script>alert(1)</script> & c"}, "major": None},
                     type_="DYNAMIC_TYPE_FORWARD", orig=evil_orig, author="A&B<b>")
        with patch(FETCH_PATCH, AsyncMock(return_value=evil)):
            result = await BilibiliStatus(url=f"https://t.bilibili.com/{DYN_ID}").get_item()
        for field in ("text", "content"):
            out = result[field]
            assert "<script>" not in out and "<u>" not in out and "<i>" not in out
            assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
            assert "A&amp;B&lt;b&gt;" in out
            assert '"onclick="' not in out
        assert "x &gt; y" in result["content"]
        # Our own markup survives.
        assert result["text"].startswith("<b><a href=")
        assert "<blockquote>" in result["content"]

    @pytest.mark.asyncio
    async def test_long_text_becomes_long_message(self):
        long_item = _item({"desc": {"text": "长" * 600}, "major": None})
        with patch(FETCH_PATCH, AsyncMock(return_value=long_item)):
            result = await BilibiliStatus(url=f"https://t.bilibili.com/{DYN_ID}").get_item()
        assert result["message_type"] == MessageType.LONG

    @pytest.mark.asyncio
    async def test_short_link_is_expanded(self):
        with patch.object(bili_utils, "expand_short_link", AsyncMock(return_value=f"https://m.bilibili.com/opus/{DYN_ID}?share=1")), \
                patch(FETCH_PATCH, AsyncMock(return_value=OPUS_ITEM)) as fetch:
            await BilibiliStatus(url="https://b23.tv/abc").get_item()
        fetch.assert_awaited_once_with(DYN_ID)

    @pytest.mark.asyncio
    async def test_non_dynamic_url_rejected(self):
        with pytest.raises(ScraperError, match="不是 B 站动态链接"):
            await BilibiliStatus(url="https://www.bilibili.com/video/BV1xx411c7mD").get_item()


# ---------------------------------------------------------------------------
# URL helpers and routing
# ---------------------------------------------------------------------------


class TestDynamicUrlHelpers:
    @pytest.mark.parametrize(
        "url, expected",
        [
            (f"https://t.bilibili.com/{DYN_ID}", DYN_ID),
            (f"https://t.bilibili.com/{DYN_ID}?share_source=x", DYN_ID),
            (f"https://www.bilibili.com/opus/{DYN_ID}", DYN_ID),
            (f"https://m.bilibili.com/opus/{DYN_ID}/", DYN_ID),
            (f"https://m.bilibili.com/dynamic/{DYN_ID}", DYN_ID),
            (f"bilibili.com/opus/{DYN_ID}", DYN_ID),
            ("https://www.bilibili.com/video/BV1xx411c7mD", None),
            ("https://t.bilibili.com/123", None),
            (f"https://evil.com/opus/{DYN_ID}", None),
        ],
    )
    def test_extract_dynamic_id(self, url, expected):
        assert bili_utils.extract_dynamic_id(url) == expected

    @pytest.mark.parametrize(
        "url, expected",
        [("https://b23.tv/abc", True), ("bili2233.cn/x", True), ("https://www.bilibili.com/video/x", False)],
    )
    def test_is_short_link(self, url, expected):
        assert bili_utils.is_short_link(url) is expected


class TestUrlRouting:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url",
        [
            f"https://t.bilibili.com/{DYN_ID}",
            f"https://www.bilibili.com/opus/{DYN_ID}?spm_id_from=x",
            f"https://m.bilibili.com/dynamic/{DYN_ID}",
        ],
    )
    async def test_dynamic_urls_are_social_media(self, url):
        meta = (await get_url_metadata(url)).to_dict()
        assert meta["source"] == "bilibili_status"
        assert meta["content_type"] == "social_media"
        assert "?" not in meta["url"]

    @pytest.mark.asyncio
    async def test_video_url_unchanged(self):
        meta = (await get_url_metadata("https://www.bilibili.com/video/BV1xx411c7mD?p=2")).to_dict()
        assert (meta["source"], meta["content_type"]) == ("bilibili", "video")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "target, source, content_type",
        [
            (f"https://m.bilibili.com/opus/{DYN_ID}?share=1", "bilibili_status", "social_media"),
            ("https://m.bilibili.com/video/BV1xx411c7mD?share=1", "bilibili", "video"),
        ],
    )
    async def test_short_link_classified_by_target(self, target, source, content_type):
        with patch.object(bili_utils, "expand_short_link", AsyncMock(return_value=target)):
            meta = (await get_url_metadata("https://b23.tv/abc")).to_dict()
        assert (meta["source"], meta["content_type"]) == (source, content_type)

    @pytest.mark.asyncio
    async def test_short_link_expansion_failure_falls_back_to_video(self):
        with patch.object(bili_utils, "expand_short_link", AsyncMock(side_effect=httpx.ConnectError("x"))):
            meta = (await get_url_metadata("https://b23.tv/abc")).to_dict()
        assert (meta["source"], meta["url"]) == ("bilibili", "https://b23.tv/abc")

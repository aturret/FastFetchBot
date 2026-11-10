"""Tests for fastfetchbot_file_export.bilibili_guest (no-login Bilibili download)."""

import os
from unittest.mock import patch

import httpx
import pytest

from fastfetchbot_file_export import bilibili_guest as guest
from fastfetchbot_file_export.bilibili_guest import GuestDownloadError, guest_download

BV = "BV1xx411c7mD"
URL = f"https://www.bilibili.com/video/{BV}"
_RealClient = httpx.Client

VIEW = {
    "bvid": BV,
    "cid": 111,
    "title": "测试/视频标题很长很长很长",
    "desc": "简介",
    "pic": "https://i0.hdslb.com/pic.jpg",
    "pubdate": 1704067200,
    "duration": 300,
    "owner": {"mid": 42, "name": "UP主"},
    "stat": {"view": 100, "danmaku": 20, "like": 30},
    "dimension": {"width": 1920, "height": 1080, "rotate": 0},
    "pages": [
        {"page": 1, "cid": 111, "duration": 100, "dimension": {"width": 1920, "height": 1080, "rotate": 0}},
        {"page": 2, "cid": 222, "duration": 200, "dimension": {"width": 1080, "height": 1920, "rotate": 0}},
    ],
}
MIRROR = "https://upos-sz-mirrorcos.bilivideo.com/ugc/x.mp4?e=1"
STABLE = "https://upos-sz-upcdnbda2.bilivideo.com/ugc/x.mp4?e=1"
PRIMARY = "https://cn-gd-fx-01.bilivideo.com/ugc/x.mp4?e=1"


class FakeBili:
    """Routes requests like the real API; records what was sent."""

    def __init__(self, *, spi_ok=True, view=None, playurl=None, cdn=None):
        self.spi_ok = spi_ok
        self.view = view if view is not None else {"code": 0, "data": VIEW}
        self.playurl = playurl if playurl is not None else {
            "code": 0,
            "data": {"quality": 32, "durl": [{"url": PRIMARY, "backup_url": [MIRROR]}]},
        }
        self.cdn = cdn if cdn is not None else {STABLE: (200, b"video-bytes")}
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/x/frontend/finger/spi":
            if not self.spi_ok:
                return httpx.Response(500)
            return httpx.Response(200, json={"code": 0, "data": {"b_3": "B3", "b_4": "B4"}})
        if path == "/x/web-interface/view":
            if isinstance(self.view, int):
                return httpx.Response(self.view)
            return httpx.Response(200, json=self.view)
        if path == "/x/player/playurl":
            return httpx.Response(200, json=self.playurl)
        status, body = self.cdn.get(str(request.url), (567, b""))
        return httpx.Response(status, content=body)

    def run(self, url=URL, tmp_path=None):
        transport = httpx.MockTransport(self.handler)
        with patch.object(guest.httpx, "Client", lambda **kw: _RealClient(transport=transport, **kw)):
            return guest_download(url, str(tmp_path))

    def request_to(self, path):
        return next(r for r in self.requests if r.url.path == path)


class TestGuestDownloadHappyPath:
    def test_downloads_file_and_maps_metadata(self, tmp_path):
        fake = FakeBili()
        out = fake.run(tmp_path=tmp_path)

        assert os.path.dirname(out["file_path"]) == str(tmp_path)
        assert "/" not in os.path.basename(out["file_path"]).replace(str(tmp_path), "")
        assert out["file_path"].endswith(f"-{BV}.mp4")
        with open(out["file_path"], "rb") as f:
            assert f.read() == b"video-bytes"
        assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())

        info = out["content_info"]
        assert info["id"] == BV
        assert info["uploader"] == "UP主"
        assert info["uploader_id"] == 42
        assert info["view_count"] == 100
        assert info["comment_count"] == 20
        assert info["like_count"] == 30
        assert info["timestamp"] == 1704067200
        assert info["duration"] == 100
        assert info["formats"] == [{"aspect_ratio": round(1920 / 1080, 3)}]

    def test_sends_guest_cookies_referer_and_quality(self, tmp_path):
        fake = FakeBili()
        fake.run(tmp_path=tmp_path)
        play = fake.request_to("/x/player/playurl")
        assert "buvid3=B3" in play.headers["cookie"]
        assert "buvid4=B4" in play.headers["cookie"]
        assert play.headers["referer"] == "https://www.bilibili.com/"
        assert play.url.params["qn"] == "64"
        assert play.url.params["fnval"] == "1"
        assert play.url.params["cid"] == "111"

    def test_selects_requested_page(self, tmp_path):
        fake = FakeBili()
        out = fake.run(url=f"{URL}?p=2", tmp_path=tmp_path)
        assert fake.request_to("/x/player/playurl").url.params["cid"] == "222"
        assert out["content_info"]["duration"] == 200
        assert out["content_info"]["formats"][0]["aspect_ratio"] < 1

    def test_out_of_range_page_uses_first(self, tmp_path):
        fake = FakeBili()
        fake.run(url=f"{URL}?p=9", tmp_path=tmp_path)
        assert fake.request_to("/x/player/playurl").url.params["cid"] == "111"

    def test_aid_url_queries_by_aid(self, tmp_path):
        fake = FakeBili()
        fake.run(url="https://www.bilibili.com/video/av170001", tmp_path=tmp_path)
        assert fake.request_to("/x/web-interface/view").url.params["aid"] == "170001"
        assert fake.request_to("/x/player/playurl").url.params["bvid"] == BV

    def test_spi_failure_is_not_fatal(self, tmp_path):
        fake = FakeBili(spi_ok=False)
        out = fake.run(tmp_path=tmp_path)
        assert os.path.exists(out["file_path"])


class TestCdnFallback:
    def test_candidate_order_prefers_rewritten_backup(self):
        assert guest._candidate_urls({"url": PRIMARY, "backup_url": [MIRROR]}) == [STABLE, MIRROR, PRIMARY]

    def test_falls_through_to_next_candidate(self, tmp_path):
        fake = FakeBili(cdn={STABLE: (567, b""), MIRROR: (200, b"from-mirror")})
        out = fake.run(tmp_path=tmp_path)
        with open(out["file_path"], "rb") as f:
            assert f.read() == b"from-mirror"

    def test_all_candidates_fail(self, tmp_path):
        fake = FakeBili(cdn={})
        with pytest.raises(GuestDownloadError, match="所有下载节点都失败（HTTP 567）"):
            fake.run(tmp_path=tmp_path)
        assert list(tmp_path.iterdir()) == []


class TestGuestErrors:
    @pytest.mark.parametrize(
        "view, reason",
        [
            (412, "风控拦截"),
            (500, "HTTP 500"),
            ({"code": -404, "message": "啥都木有"}, "视频不存在或已删除"),
            ({"code": 62002, "message": "x"}, "稿件不可见"),
            ({"code": -352, "message": "x"}, "风控拦截"),
            ({"code": 0, "data": None}, "数据结构异常"),
            ([], "数据结构异常"),
            ("ok", "数据结构异常"),
        ],
    )
    def test_view_errors(self, tmp_path, view, reason):
        with pytest.raises(GuestDownloadError, match=reason):
            FakeBili(view=view).run(tmp_path=tmp_path)

    def test_playurl_without_durl(self, tmp_path):
        fake = FakeBili(playurl={"code": 0, "data": {"quality": 32, "dash": {}}})
        with pytest.raises(GuestDownloadError, match="没有可用的游客下载地址"):
            fake.run(tmp_path=tmp_path)

    def test_invalid_url(self, tmp_path):
        with pytest.raises(GuestDownloadError, match="无法从链接中识别"):
            guest_download("https://www.bilibili.com/read/cv1", str(tmp_path))

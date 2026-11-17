"""Tests for Zhihu features borrowed from ParseHub's approach:
x-zse-96 signing, real API error messages, formula-image filtering, pin media
sizes, and question-only / appview / Zhihu Daily links.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fastfetchbot_shared.exceptions import ScraperError

ZHIHU = "fastfetchbot_shared.services.scrapers.zhihu"


@pytest.fixture
def zhihu_mod():
    """Import the module with templates and the shared client mocked."""
    import fastfetchbot_shared.services.scrapers.zhihu as mod

    template = MagicMock()
    template.render.return_value = "<p>rendered</p>"
    with patch.object(mod, "short_text_template", template), \
            patch.object(mod, "content_template", template), \
            patch.object(mod, "zhihu_client", MagicMock()), \
            patch.object(mod, "ZHIHU_API_COOKIE", None), \
            patch.object(mod, "ZHIHU_COOKIES", None):
        yield mod


def _response(payload=None, status=200, json_error=False):
    resp = MagicMock()
    resp.status_code = status
    if json_error:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = payload
    return resp


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------


class TestSignature:
    URL = "https://www.zhihu.com/api/v4/answers/603067076?include=content,voteup_count"
    D_C0 = "AABBccdd1234=|1700000000"

    def test_matches_parsehub_reference(self):
        """Reference generated with ParseHub's original implementation and the same fixed IV."""
        from fastfetchbot_shared.services.scrapers.zhihu.signature import get_x_zse_96

        assert get_x_zse_96(self.URL, self.D_C0, iv=list(range(16))) == (
            "2.0_wNabc4U5sA9oMVwT7s91XeUb30uj1KjRdCv2HCzDZLkjnd6LtWxp8dmfqxxnpR66"
        )

    def test_format_and_random_iv(self):
        from fastfetchbot_shared.services.scrapers.zhihu.signature import get_x_zse_96

        a, b = get_x_zse_96(self.URL, self.D_C0), get_x_zse_96(self.URL, self.D_C0)
        assert a.startswith("2.0_") and len(a) == 68
        assert a != b  # random IV per call, like the browser

    def test_query_is_part_of_signature(self):
        from fastfetchbot_shared.services.scrapers.zhihu.signature import get_x_zse_96

        iv = list(range(16))
        assert get_x_zse_96(self.URL, self.D_C0, iv=iv) != get_x_zse_96(self.URL.split("?")[0], self.D_C0, iv=iv)


# ---------------------------------------------------------------------------
# API helper and request headers
# ---------------------------------------------------------------------------


class TestApiGetJson:
    @pytest.mark.asyncio
    async def test_returns_dict(self, zhihu_mod):
        with patch.object(zhihu_mod, "get_response", AsyncMock(return_value=_response({"id": 1}))):
            assert await zhihu_mod._zhihu_api_get_json("u") == {"id": 1}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response, reason",
        [
            (_response({"error": {"code": 10003, "message": "请求参数异常，请升级客户端后重试"}}, status=403),
             "知乎接口错误 10003：请求参数异常，请升级客户端后重试"),
            (_response({"error": "blocked"}), "知乎接口错误 None：blocked"),
            (_response(json_error=True, status=502), r"不是 JSON（HTTP 502）"),
            (_response([1, 2]), "不是 JSON 对象"),
            (_response({"msg": "x"}, status=500), "知乎接口返回 HTTP 500"),
        ],
    )
    async def test_errors(self, zhihu_mod, response, reason):
        with patch.object(zhihu_mod, "get_response", AsyncMock(return_value=response)):
            with pytest.raises(ScraperError, match=reason):
                await zhihu_mod._zhihu_api_get_json("u")

    @pytest.mark.asyncio
    async def test_network_error(self, zhihu_mod):
        with patch.object(zhihu_mod, "get_response", AsyncMock(side_effect=httpx.ConnectTimeout("t"))):
            with pytest.raises(ScraperError, match="知乎请求失败：ConnectTimeout"):
                await zhihu_mod._zhihu_api_get_json("u")


class TestRequestHeaders:
    def test_plain_api_uses_default_headers(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/pin/1", cookie="z_c0=Z; d_c0=D")
        z.method = "api"
        assert z._request_headers("https://www.zhihu.com/api/v4/pins/1") is z.headers

    def test_signed_api_adds_signature(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/pin/1", cookie="z_c0=Z; d_c0=D0|123")
        z.method = "signed_api"
        with patch.object(zhihu_mod, "get_x_zse_96", return_value="2.0_sig") as sign:
            headers = z._request_headers("https://www.zhihu.com/api/v4/answers/2?include=content,voteup_count")
        sign.assert_called_once_with("https://www.zhihu.com/api/v4/answers/2?include=content,voteup_count", "D0|123")
        assert headers["x-zse-96"] == "2.0_sig"
        assert headers["x-zse-93"] == "101_3_3.0"
        assert headers["Cookie"] == "z_c0=Z; d_c0=D0|123"
        assert headers["User-Agent"].startswith("Mozilla/5.0")

    def test_env_cookie_with_d_c0_enables_signing(self, zhihu_mod):
        with patch.object(zhihu_mod, "ZHIHU_COOKIES", "z_c0=Z; d_c0=D0|123"):
            z = zhihu_mod.Zhihu(url="https://www.zhihu.com/pin/1")
        z.method = "signed_api"
        with patch.object(zhihu_mod, "get_x_zse_96", return_value="2.0_sig") as sign:
            headers = z._request_headers("https://www.zhihu.com/api/v4/pins/1")
        assert sign.call_args.args[1] == "D0|123"
        assert headers["Cookie"] == "z_c0=Z; d_c0=D0|123"

    def test_signed_api_without_d_c0(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/pin/1", cookie="z_c0=Z")
        z.method = "signed_api"
        with pytest.raises(ScraperError, match="d_c0"):
            z._request_headers("https://www.zhihu.com/api/v4/pins/1")


# ---------------------------------------------------------------------------
# Fallback loop
# ---------------------------------------------------------------------------


def _loop_zhihu(zhihu_mod, behaviour):
    """Zhihu answer whose _get_zhihu_answer behaves per method: an Exception to raise, or a title."""
    z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1/answer/2")
    calls = []

    async def fake_answer():
        calls.append(z.method)
        outcome = behaviour[z.method]
        if isinstance(outcome, Exception):
            raise outcome
        z.title = outcome

    z._get_request_url = AsyncMock()
    z._get_zhihu_answer = fake_answer
    z._zhihu_short_text_process = MagicMock()
    z._zhihu_content_process = MagicMock()
    z.text = ""
    return z, calls


class TestFallbackLoop:
    @pytest.mark.asyncio
    async def test_all_methods_fail_reports_each_reason(self, zhihu_mod):
        z, calls = _loop_zhihu(zhihu_mod, {
            "api": ScraperError("知乎接口错误 10003：请求参数异常"),
            "signed_api": ScraperError("签名请求需要 Cookie 里的 d_c0"),
            "fxzhihu": RuntimeError("fx down"),
        })
        with pytest.raises(ScraperError) as exc_info:
            await z._get_zhihu_item()
        message = str(exc_info.value)
        assert calls == ["api", "signed_api", "fxzhihu"]
        assert message.startswith("知乎内容获取失败：")
        assert "api: 知乎接口错误 10003：请求参数异常" in message
        assert "signed_api: 签名请求需要 Cookie 里的 d_c0" in message
        assert "fxzhihu: fx down" in message
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    @pytest.mark.asyncio
    async def test_signed_api_success_skips_fxzhihu(self, zhihu_mod):
        z, calls = _loop_zhihu(zhihu_mod, {
            "api": ScraperError("知乎接口错误 10003：x"),
            "signed_api": "回答标题",
            "fxzhihu": AssertionError("should not run"),
        })
        await z._get_zhihu_item()
        assert calls == ["api", "signed_api"]
        assert z.title == "回答标题"

    @pytest.mark.asyncio
    async def test_signed_api_first_when_d_c0_present(self, zhihu_mod):
        with patch.object(zhihu_mod, "ZHIHU_COOKIES", "z_c0=Z; d_c0=D"):
            z, calls = _loop_zhihu(zhihu_mod, {
                "signed_api": ScraperError("知乎接口错误 40362：x"),
                "api": ScraperError("知乎接口错误 10003：x"),
                "fxzhihu": "标题",
            })
        await z._get_zhihu_item()
        assert calls == ["signed_api", "api", "fxzhihu"]

    @pytest.mark.asyncio
    async def test_signed_api_success_needs_one_request(self, zhihu_mod):
        with patch.object(zhihu_mod, "ZHIHU_COOKIES", "z_c0=Z; d_c0=D"):
            z, calls = _loop_zhihu(zhihu_mod, {"signed_api": "标题"})
        await z._get_zhihu_item()
        assert calls == ["signed_api"]

    def test_method_order(self, zhihu_mod):
        default = ["api", "signed_api", "fxzhihu"]
        with patch.object(zhihu_mod, "ZHIHU_COOKIES", "z_c0=Z"):
            assert zhihu_mod.Zhihu(url="https://www.zhihu.com/pin/1")._method_order(default) == default
        with patch.object(zhihu_mod, "ZHIHU_COOKIES", "z_c0=Z; d_c0=D"):
            z = zhihu_mod.Zhihu(url="https://www.zhihu.com/pin/1")
        assert z._method_order(default) == ["signed_api", "api", "fxzhihu"]
        assert z._method_order(["fxzhihu"]) == ["fxzhihu"]

    @pytest.mark.asyncio
    async def test_unknown_link_rejected_without_requests(self, zhihu_mod):
        z, calls = _loop_zhihu(zhihu_mod, {})
        z.urlparser = zhihu_mod.urlparse("https://www.zhihu.com/people/someone")
        with pytest.raises(ScraperError, match="不支持的知乎链接"):
            await z._get_zhihu_item()
        assert calls == []


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


class TestMedia:
    def test_formula_and_placeholder_images_are_not_media(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = (
            '<p>文字<img src="https://www.zhihu.com/equation?tex=x%5E2" alt="x^2"/></p>'
            '<img src="data:image/svg+xml;utf8,&lt;svg/&gt;"/>'
            '<img src="https://pic1.zhimg.com/v2-abc_r.jpg"/>'
        )
        z._zhihu_short_text_process()
        assert [m.url for m in z.media_files] == ["https://pic1.zhimg.com/v2-abc_r.jpg"]
        rendered = zhihu_mod.short_text_template.render.call_args.kwargs["data"]["content"]
        assert "/equation?tex=" in rendered  # formula stays inline

    def test_pin_image_has_size(self, zhihu_mod):
        data = {
            "author": {"name": "A", "url_token": "a"}, "created": 1, "updated": 1,
            "content": [{"type": "image", "original_url": "https://pic.jpg", "width": 1080, "height": 1440}],
        }
        media = zhihu_mod.Zhihu._resolve_status_api_data(data)["media_files"][0]
        assert (media.media_type, media.url, media.width, media.height) == ("image", "https://pic.jpg", 1080, 1440)

    @pytest.mark.parametrize(
        "content, expected",
        [
            (  # dict playlist: fhd wins, `url` field accepted, duration from video_info
                {"type": "video", "video_info": {"duration": 12.6, "playlist": {
                    "sd": {"url": "https://sd.mp4", "width": 640, "height": 360},
                    "fhd": {"url": "https://fhd.mp4", "width": 1920, "height": 1080},
                    "hd": {"play_url": "https://hd.mp4", "width": 1280, "height": 720},
                }}},
                ("https://fhd.mp4", 1920, 1080, 12),
            ),
            (  # play_url preferred over url within the same stream
                {"type": "video", "video_info": {"playlist": {
                    "hd": {"play_url": "https://play.mp4", "url": "https://plain.mp4", "width": 1280, "height": 720},
                }}},
                ("https://play.mp4", 1280, 720, None),
            ),
            (  # list playlist with quality keys
                {"type": "video", "duration": 30, "playlist": [
                    {"quality": "ld", "url": "https://ld.mp4"},
                    {"quality": "hd", "url": "https://hd.mp4", "width": 720, "height": 1280},
                ]},
                ("https://hd.mp4", 720, 1280, 30),
            ),
            (  # streams without an address are skipped
                {"type": "video", "video_info": {"playlist": {
                    "fhd": {"width": 1920}, "sd": {"url": "https://sd.mp4"},
                }}},
                ("https://sd.mp4", None, None, None),
            ),
        ],
    )
    def test_pin_video_selection(self, zhihu_mod, content, expected):
        data = {"author": {"name": "A", "url_token": "a"}, "created": 1, "updated": 1, "content": [content]}
        media = zhihu_mod.Zhihu._resolve_status_api_data(data)["media_files"][0]
        assert (media.url, media.width, media.height, media.duration) == expected

    def test_pin_video_without_streams(self, zhihu_mod):
        data = {"author": {"name": "A", "url_token": "a"}, "created": 1, "updated": 1,
                "content": [{"type": "video", "video_info": {"playlist": {}}}]}
        assert zhihu_mod.Zhihu._resolve_status_api_data(data)["media_files"] == []


# ---------------------------------------------------------------------------
# Link types
# ---------------------------------------------------------------------------


class TestLinkTypes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("url", [
        "https://zhuanlan.zhihu.com/appview/p/35142635",
        "https://www.zhihu.com/appview/p/35142635?utm=x",
    ])
    async def test_appview_is_article(self, zhihu_mod, url):
        z = zhihu_mod.Zhihu(url=url)
        await z._check_zhihu_type()
        assert (z.zhihu_type, z.article_id) == ("article", "35142635")
        assert z.url == "https://zhuanlan.zhihu.com/p/35142635"
        assert z.urlparser.netloc == "zhuanlan.zhihu.com"

    @pytest.mark.asyncio
    async def test_question_only_link(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/19998424/")
        await z._check_zhihu_type()
        assert (z.zhihu_type, z.question_id) == ("question", "19998424")

    @pytest.mark.asyncio
    async def test_question_resolves_first_answer(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/19998424")
        await z._check_zhihu_type()
        api = AsyncMock(return_value={"data": [{"id": 603067076}]})
        with patch.object(zhihu_mod, "_zhihu_api_get_json", api):
            await z._resolve_question_answer()
        assert "/questions/19998424/answers?limit=1" in api.call_args.args[0]
        assert (z.zhihu_type, z.answer_id, z.method) == ("answer", "603067076", "api")  # original method restored
        assert z.url == "https://www.zhihu.com/question/19998424/answer/603067076"
        assert z.urlparser.path == "/question/19998424/answer/603067076"

    @pytest.mark.asyncio
    async def test_question_lookup_signed_first_then_unsigned(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1", cookie="z_c0=Z; d_c0=D")
        await z._check_zhihu_type()
        api = AsyncMock(side_effect=[ScraperError("知乎接口错误 10003：x"), {"data": [{"id": 9}]}])
        with patch.object(zhihu_mod, "_zhihu_api_get_json", api):
            await z._resolve_question_answer()
        assert z.answer_id == "9"
        assert "x-zse-96" in api.call_args_list[0].kwargs["headers"]
        assert "x-zse-96" not in api.call_args_list[1].kwargs["headers"]

    @pytest.mark.asyncio
    async def test_question_lookup_keeps_caller_method(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1", method="fxzhihu")
        await z._check_zhihu_type()
        with patch.object(zhihu_mod, "_zhihu_api_get_json", AsyncMock(return_value={"data": [{"id": 9}]})):
            await z._resolve_question_answer()
        assert z.method == "fxzhihu"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [
        {},                              # no "data" key
        {"data": "oops"},                # not a list
        {"data": {"0": {"id": 1}}},      # mapping instead of list
        {"data": ["123"]},               # entry is not a mapping
        {"data": [{"title": "no id"}]},  # entry without id
    ])
    async def test_malformed_answers_try_next_method(self, zhihu_mod, bad):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1", cookie="z_c0=Z; d_c0=D")
        await z._check_zhihu_type()
        api = AsyncMock(side_effect=[bad, {"data": [{"id": 7}]}])
        with patch.object(zhihu_mod, "_zhihu_api_get_json", api):
            await z._resolve_question_answer()
        assert z.answer_id == "7"
        assert api.await_count == 2

    @pytest.mark.asyncio
    async def test_malformed_answers_everywhere_raises_typed_error(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1", cookie="z_c0=Z; d_c0=D")
        await z._check_zhihu_type()
        with patch.object(zhihu_mod, "_zhihu_api_get_json", AsyncMock(return_value={"data": "oops"})):
            with pytest.raises(ScraperError, match="知乎问题的回答获取失败：signed_api: 知乎问题的回答列表数据结构异常；api: "):
                await z._resolve_question_answer()
        assert z.method == "api"  # caller's method restored

    @pytest.mark.asyncio
    async def test_question_without_answers(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1")
        await z._check_zhihu_type()
        with patch.object(zhihu_mod, "_zhihu_api_get_json", AsyncMock(return_value={"data": []})):
            with pytest.raises(ScraperError, match="还没有回答"):
                await z._resolve_question_answer()

    @pytest.mark.asyncio
    async def test_question_lookup_all_fail(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/question/1")
        await z._check_zhihu_type()
        with patch.object(zhihu_mod, "_zhihu_api_get_json", AsyncMock(side_effect=ScraperError("知乎接口错误 403：x"))):
            with pytest.raises(ScraperError, match="知乎问题的回答获取失败：api: 知乎接口错误 403：x；signed_api: 签名请求需要"):
                await z._resolve_question_answer()

    @pytest.mark.asyncio
    async def test_daily_story_resolves_origin(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://daily.zhihu.com/story/9781234")
        story = {"body": '<div><a href="https://www.zhihu.com/question/1/answer/2">查看知乎原文（123 条讨论）</a></div>'}
        api = AsyncMock(return_value=story)
        with patch.object(zhihu_mod, "_zhihu_api_get_json", api):
            await z._resolve_daily_url()
        assert api.call_args.args[0] == "https://daily.zhihu.com/api/7/story/9781234"
        assert z.url == "https://www.zhihu.com/question/1/answer/2"
        await z._check_zhihu_type()
        assert (z.zhihu_type, z.answer_id) == ("answer", "2")

    @pytest.mark.asyncio
    async def test_daily_story_without_origin(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://daily.zhihu.com/story/9781234")
        with patch.object(zhihu_mod, "_zhihu_api_get_json", AsyncMock(return_value={"body": "<p>原创</p>"})):
            with pytest.raises(ScraperError, match="没有对应的知乎原文"):
                await z._resolve_daily_url()

    @pytest.mark.asyncio
    async def test_non_daily_link_makes_no_request(self, zhihu_mod):
        z = zhihu_mod.Zhihu(url="https://www.zhihu.com/pin/1")
        api = AsyncMock()
        with patch.object(zhihu_mod, "_zhihu_api_get_json", api):
            await z._resolve_daily_url()
        api.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("url", [
        "https://www.zhihu.com/question/19998424",
        "https://zhuanlan.zhihu.com/appview/p/35142635",
        "https://www.zhihu.com/appview/p/35142635",
        "https://daily.zhihu.com/story/9781234",
    ])
    async def test_new_links_route_to_zhihu(self, url):
        from fastfetchbot_shared.utils.parse import get_url_metadata

        meta = (await get_url_metadata(url)).to_dict()
        assert (meta["source"], meta["content_type"]) == ("zhihu", "social_media")

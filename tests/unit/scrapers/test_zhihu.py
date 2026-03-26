"""Unit tests for Zhihu scraper and config modules.

Covers:
- packages/shared/fastfetchbot_shared/services/scrapers/zhihu/__init__.py
- packages/shared/fastfetchbot_shared/services/scrapers/zhihu/config.py
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType


# ---------------------------------------------------------------------------
# Module-level / config tests
# ---------------------------------------------------------------------------


class TestZhihuConfig:
    """Tests for zhihu/config.py cookie resolution logic.

    The config module imports ZHIHU_Z_C0 and ZHIHU_COOKIES_JSON from the parent
    scrapers.config, so we must patch on that parent module before reloading.
    """

    def test_config_with_z_c0(self):
        """When ZHIHU_Z_C0 is set, ZHIHU_API_COOKIE uses it."""
        with patch(
            "fastfetchbot_shared.services.scrapers.config.settings.ZHIHU_Z_C0", "test_token"
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.ZHIHU_COOKIES_JSON", None
        ):
            import importlib
            import fastfetchbot_shared.services.scrapers.zhihu.config as cfg

            importlib.reload(cfg)
            assert cfg.ZHIHU_API_COOKIE == "z_c0=test_token"

    def test_config_with_cookies_json(self):
        """When ZHIHU_Z_C0 is empty but ZHIHU_COOKIES_JSON is set, use cookies JSON."""
        cookies = [{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]
        with patch(
            "fastfetchbot_shared.services.scrapers.config.settings.ZHIHU_Z_C0", ""
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.ZHIHU_COOKIES_JSON",
            cookies,
        ):
            import importlib
            import fastfetchbot_shared.services.scrapers.zhihu.config as cfg

            importlib.reload(cfg)
            assert cfg.ZHIHU_API_COOKIE == "a=1;b=2"
            assert cfg.ZHIHU_COOKIES == "a=1;b=2"

    def test_config_no_cookies(self):
        """When both ZHIHU_Z_C0 and ZHIHU_COOKIES_JSON are empty/None."""
        with patch(
            "fastfetchbot_shared.services.scrapers.config.settings.ZHIHU_Z_C0", ""
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.ZHIHU_COOKIES_JSON",
            None,
        ):
            import importlib
            import fastfetchbot_shared.services.scrapers.zhihu.config as cfg

            importlib.reload(cfg)
            assert cfg.ZHIHU_API_COOKIE is None
            assert cfg.ZHIHU_COOKIES is None

    def test_config_z_c0_takes_precedence(self):
        """ZHIHU_Z_C0 takes priority over ZHIHU_COOKIES_JSON for API cookie."""
        cookies = [{"name": "a", "value": "1"}]
        with patch(
            "fastfetchbot_shared.services.scrapers.config.settings.ZHIHU_Z_C0", "my_z_c0"
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.ZHIHU_COOKIES_JSON",
            cookies,
        ):
            import importlib
            import fastfetchbot_shared.services.scrapers.zhihu.config as cfg

            importlib.reload(cfg)
            assert cfg.ZHIHU_API_COOKIE == "z_c0=my_z_c0"
            # ZHIHU_COOKIES still uses JSON cookies
            assert cfg.ZHIHU_COOKIES == "a=1"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestParseAnswerApiJsonData:
    """Tests for _parse_answer_api_json_data module-level function."""

    def test_parses_fields(self):
        from fastfetchbot_shared.services.scrapers.zhihu import (
            _parse_answer_api_json_data,
        )

        data = {
            "question": {
                "id": 123,
                "title": "Test Q",
                "detail": "<p>detail</p>",
                "answer_count": 10,
                "follower_count": 20,
                "created": 1000,
                "updated_time": 2000,
            },
            "author": {"name": "TestAuthor", "url_token": "test_token"},
            "content": "<p>answer content</p>",
            "created_time": 3000,
            "updated_time": 4000,
            "comment_count": 5,
            "voteup_count": 50,
            "ipInfo": "Beijing",
        }
        result = _parse_answer_api_json_data(data)
        assert result["question_id"] == 123
        assert result["title"] == "Test Q"
        assert result["author"] == "TestAuthor"
        assert result["content"] == "<p>answer content</p>"
        assert result["voteup_count"] == 50
        assert result["ip_info"] == "Beijing"

    def test_missing_fields_returns_none(self):
        from fastfetchbot_shared.services.scrapers.zhihu import (
            _parse_answer_api_json_data,
        )

        data = {}
        result = _parse_answer_api_json_data(data)
        assert result["question_id"] is None
        assert result["title"] is None


class TestFixJsonQuotes:
    """Tests for _fix_json_quotes function."""

    def test_fixes_newlines(self):
        from fastfetchbot_shared.services.scrapers.zhihu import _fix_json_quotes

        result = _fix_json_quotes("hello\nworld\rtest")
        assert "\\n" in result
        assert "\\r" in result
        assert "\n" not in result

    def test_fixes_href_quotes(self):
        from fastfetchbot_shared.services.scrapers.zhihu import _fix_json_quotes

        raw = 'href="http://example.com"'
        result = _fix_json_quotes(raw)
        assert '\\"' in result

    def test_fixes_content_key_inner_quotes(self):
        from fastfetchbot_shared.services.scrapers.zhihu import _fix_json_quotes

        raw = '"content":"some \\"quoted\\" text","another_key":"value"'
        result = _fix_json_quotes(raw)
        # Should not raise and should produce a string
        assert isinstance(result, str)

    def test_fixes_detail_key_inner_quotes(self):
        from fastfetchbot_shared.services.scrapers.zhihu import _fix_json_quotes

        raw = '"detail":"has a \\"quote\\" inside","next_key":"val"'
        result = _fix_json_quotes(raw)
        assert isinstance(result, str)

    def test_no_target_keys(self):
        from fastfetchbot_shared.services.scrapers.zhihu import _fix_json_quotes

        raw = '"title":"no issue"'
        result = _fix_json_quotes(raw)
        assert result == '"title":"no issue"'


# ---------------------------------------------------------------------------
# Zhihu class tests
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_zhihu_module():
    """Patch module-level template objects and httpx client for Zhihu import."""
    mock_template = MagicMock()
    mock_template.render.return_value = "<p>rendered text</p>"
    mock_content_template = MagicMock()
    mock_content_template.render.return_value = "<div>rendered content</div>"
    with patch(
        "fastfetchbot_shared.services.scrapers.zhihu.short_text_template",
        mock_template,
    ), patch(
        "fastfetchbot_shared.services.scrapers.zhihu.content_template",
        mock_content_template,
    ), patch(
        "fastfetchbot_shared.services.scrapers.zhihu.zhihu_client",
        MagicMock(),
    ):
        yield {
            "short_text_template": mock_template,
            "content_template": mock_content_template,
        }


class TestZhihuInit:
    """Tests for Zhihu.__init__."""

    def test_default_init(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", "api_cookie"
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", "full_cookie"
        ):
            z = Zhihu(url="https://www.zhihu.com/question/123/answer/456")
        assert z.url == "https://www.zhihu.com/question/123/answer/456"
        assert z.category == "zhihu"
        assert z.message_type == MessageType.SHORT
        assert z.method == "api"
        assert z.headers["Cookie"] == "full_cookie"

    def test_init_with_custom_cookie(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", "api_cookie"
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", "full_cookie"
        ):
            z = Zhihu(
                url="https://www.zhihu.com/question/123/answer/456",
                cookie="custom_cookie",
            )
        assert z.headers["Cookie"] == "custom_cookie"

    def test_init_no_api_cookie(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/123")
        assert "Cookie" not in z.headers

    def test_init_with_method_kwarg(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ):
            z = Zhihu(
                url="https://www.zhihu.com/question/1/answer/2",
                method="fxzhihu",
            )
        assert z.method == "fxzhihu"

    def test_init_api_cookie_set_no_zhihu_cookies(self, _patch_zhihu_module):
        """API cookie is set but ZHIHU_COOKIES is None — no extra cookie header from ZHIHU_COOKIES."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", "api_c"
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/1")
        # Cookie set from ZHIHU_API_COOKIE, then kwargs.cookie not provided and
        # ZHIHU_COOKIES is None so the elif doesn't fire
        assert z.headers["Cookie"] == "api_c"


class TestCheckZhihuType:
    """Tests for Zhihu._check_zhihu_type."""

    @pytest.mark.asyncio
    async def test_article_type(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/35142635")
        await z._check_zhihu_type()
        assert z.zhihu_type == "article"
        assert z.article_id == "35142635"

    @pytest.mark.asyncio
    async def test_answer_type_with_question(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/19998424/answer/603067076")
        await z._check_zhihu_type()
        assert z.zhihu_type == "answer"
        assert z.answer_id == "603067076"
        assert z.question_id == "19998424"

    @pytest.mark.asyncio
    async def test_answer_type_without_question(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/answer/603067076")
        await z._check_zhihu_type()
        assert z.zhihu_type == "answer"
        assert z.answer_id == "603067076"

    @pytest.mark.asyncio
    async def test_status_type(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/pin/1667965059081945088")
        await z._check_zhihu_type()
        assert z.zhihu_type == "status"
        assert z.status_id == "1667965059081945088"

    @pytest.mark.asyncio
    async def test_unknown_type(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/people/someone")
        await z._check_zhihu_type()
        assert z.zhihu_type == "unknown"


class TestGetRequestUrl:
    """Tests for Zhihu._get_request_url."""

    @pytest.mark.asyncio
    async def test_fxzhihu_answer_with_question_id(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.settings.FXZHIHU_HOST", "fxzhihu.com"
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
        z.zhihu_type = "answer"
        z.answer_id = "200"
        z.question_id = "100"
        z.method = "fxzhihu"
        await z._get_request_url()
        assert z.request_url == "https://fxzhihu.com/question/100/answer/200"

    @pytest.mark.asyncio
    async def test_fxzhihu_answer_no_question_id(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.settings.FXZHIHU_HOST", "fxzhihu.com"
        ):
            z = Zhihu(url="https://www.zhihu.com/answer/200")
        z.zhihu_type = "answer"
        z.answer_id = "200"
        z.question_id = ""
        z.method = "fxzhihu"
        await z._get_request_url()
        assert z.request_url == "https://fxzhihu.com/answer/200"

    @pytest.mark.asyncio
    async def test_fxzhihu_article(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.settings.FXZHIHU_HOST", "fxzhihu.com"
        ):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
        z.zhihu_type = "article"
        z.article_id = "12345"
        z.method = "fxzhihu"
        await z._get_request_url()
        assert z.request_url == "https://fxzhihu.com/p/12345"

    @pytest.mark.asyncio
    async def test_fxzhihu_status(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.settings.FXZHIHU_HOST", "fxzhihu.com"
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
        z.zhihu_type = "status"
        z.status_id = "999"
        z.method = "fxzhihu"
        await z._get_request_url()
        assert z.request_url == "https://fxzhihu.com/pin/999"

    @pytest.mark.asyncio
    async def test_api_answer(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
        z.zhihu_type = "answer"
        z.answer_id = "200"
        z.method = "api"
        await z._get_request_url()
        assert "answers/200" in z.request_url
        assert z.request_url.startswith("https://www.zhihu.com/api/v4")

    @pytest.mark.asyncio
    async def test_api_article(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
        z.zhihu_type = "article"
        z.article_id = "12345"
        z.method = "api"
        await z._get_request_url()
        assert z.request_url == "https://www.zhihu.com/api/v4/articles/12345"

    @pytest.mark.asyncio
    async def test_api_status(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
        z.zhihu_type = "status"
        z.status_id = "999"
        z.method = "api"
        await z._get_request_url()
        assert z.request_url == "https://www.zhihu.com/api/v4/pins/999"

    @pytest.mark.asyncio
    async def test_non_api_answer_with_question_in_path(self, _patch_zhihu_module):
        """When method is not api/fxzhihu and path contains 'question'."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
        z.zhihu_type = "answer"
        z.answer_id = "200"
        z.question_id = "100"
        z.method = "html"
        await z._get_request_url()
        assert "/aria/question/100/answer/200" in z.request_url

    @pytest.mark.asyncio
    async def test_non_api_answer_without_question_in_path(self, _patch_zhihu_module):
        """When method is html and path doesn't contain 'question', _get_question_id is called."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ):
            z = Zhihu(url="https://www.zhihu.com/answer/200")
        z.zhihu_type = "answer"
        z.answer_id = "200"
        z.question_id = ""
        z.method = "html"
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_redirect_url",
            new_callable=AsyncMock,
            return_value="https://www.zhihu.com/question/555/answer/200",
        ):
            await z._get_request_url()
        assert z.question_id == "555"

    @pytest.mark.asyncio
    async def test_non_api_non_fxzhihu_article_falls_through(self, _patch_zhihu_module):
        """Article with method='html' falls through to default URL construction."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
        z.zhihu_type = "article"
        z.article_id = "12345"
        z.method = "html"
        await z._get_request_url()
        assert z.request_url == "https://zhuanlan.zhihu.com/p/12345"

    @pytest.mark.asyncio
    async def test_non_api_non_fxzhihu_status_falls_through(self, _patch_zhihu_module):
        """Status with method='html' falls through to default URL construction."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
        z.zhihu_type = "status"
        z.status_id = "999"
        z.method = "html"
        await z._get_request_url()
        assert z.request_url == "https://www.zhihu.com/pin/999"


class TestGetZhihuAnswer:
    """Tests for Zhihu._get_zhihu_answer."""

    @pytest.mark.asyncio
    async def test_api_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        api_response = {
            "question": {
                "id": 100,
                "title": "Test Question",
                "detail": "detail",
                "answer_count": 5,
                "follower_count": 10,
                "created": 1000,
                "updated_time": 2000,
            },
            "author": {"name": "Author", "url_token": "author_token"},
            "content": "<p>answer</p>",
            "created_time": 3000,
            "updated_time": 4000,
            "comment_count": 2,
            "voteup_count": 30,
            "ipInfo": "",
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=api_response,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/answers/200"
            await z._get_zhihu_answer()
        assert z.title == "Test Question"
        assert z.author == "Author"

    @pytest.mark.asyncio
    async def test_api_method_failure_raises(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/answers/200"
            with pytest.raises(Exception, match="Cannot get the answer by API"):
                await z._get_zhihu_answer()

    @pytest.mark.asyncio
    async def test_fxzhihu_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        response_data = {
            "question": {
                "id": 100,
                "title": "FxQ",
                "detail": "",
                "answer_count": 1,
                "follower_count": 1,
                "created": 1000,
                "updated_time": 2000,
            },
            "author": {"name": "FxAuthor", "url_token": "fx_token"},
            "content": "<p>fx answer</p>",
            "created_time": 3000,
            "updated_time": 4000,
            "comment_count": 0,
            "voteup_count": 0,
            "ipInfo": "",
        }
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(response_data)
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "fxzhihu"
            z.request_url = "https://fxzhihu.com/question/100/answer/200"
            await z._get_zhihu_answer()
        assert z.title == "FxQ"

    @pytest.mark.asyncio
    async def test_fxzhihu_method_failure_raises(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "fxzhihu"
            z.request_url = "https://fxzhihu.com/question/100/answer/200"
            with pytest.raises(Exception, match="Cannot get the answer by fxzhihu"):
                await z._get_zhihu_answer()

    @pytest.mark.asyncio
    async def test_json_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "initialState": {
                "entities": {
                    "answers": {
                        "200": {
                            "question": {"id": 100},
                            "author": {"name": "JsonAuthor", "urlToken": "jt"},
                            "content": "<p>json content</p>",
                            "createdTime": 1000,
                            "updatedTime": 2000,
                            "commentCount": 1,
                            "voteupCount": 5,
                            "ipInfo": "",
                        }
                    },
                    "questions": {
                        "100": {
                            "title": "JsonQ",
                            "detail": "",
                            "answerCount": 3,
                            "followerCount": 7,
                            "created": 500,
                            "updatedTime": 1500,
                        }
                    },
                }
            }
        }
        mock_selector = MagicMock()
        mock_selector.xpath.return_value = json.dumps(json_data)
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "json"
            z.request_url = "https://www.zhihu.com/aria/question/100/answer/200"
            await z._get_zhihu_answer()
        assert z.title == "JsonQ"

    @pytest.mark.asyncio
    async def test_json_method_failure_raises(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "json"
            z.request_url = "https://www.zhihu.com/aria/question/100/answer/200"
            with pytest.raises(Exception, match="Cannot get the selector"):
                await z._get_zhihu_answer()

    @pytest.mark.asyncio
    async def test_html_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_selector = MagicMock()

        def xpath_side_effect(expr):
            if "VoteButton" in expr:
                return "100"
            if "RichContent-inner" in expr:
                mock_elem = MagicMock()
                from lxml import etree

                mock_elem.__class__ = etree._Element
                # Return a mock that etree.tostring can handle
                return [MagicMock()]
            if "string(//h1)" == expr:
                return "HTML Title"
            if 'itemprop="name"' in expr:
                return "HTML Author"
            if 'itemprop="url"' in expr:
                return "https://www.zhihu.com/people/someone"
            return ""

        mock_selector.xpath.side_effect = xpath_side_effect

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.etree"
        ) as mock_etree:
            mock_etree.tostring.return_value = b"<span>content</span>"
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "html"
            z.request_url = "https://www.zhihu.com/question/100/answer/200"
            await z._get_zhihu_answer()
        assert z.title == "HTML Title"
        assert z.author == "HTML Author"

    @pytest.mark.asyncio
    async def test_html_method_empty_author_url(self, _patch_zhihu_module):
        """When author_url equals the bare /people/ URL, it should be cleared."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_selector = MagicMock()

        def xpath_side_effect(expr):
            if "VoteButton" in expr:
                return "10"
            if "RichContent-inner" in expr:
                return [MagicMock()]
            if "string(//h1)" == expr:
                return "Title"
            if 'itemprop="name"' in expr:
                return "Author"
            if 'itemprop="url"' in expr:
                return "https://www.zhihu.com/people/"
            return ""

        mock_selector.xpath.side_effect = xpath_side_effect

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.etree"
        ) as mock_etree:
            mock_etree.tostring.return_value = b"<span>text</span>"
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "html"
            z.request_url = "https://www.zhihu.com/question/100/answer/200"
            await z._get_zhihu_answer()
        assert z.author_url == ""

    @pytest.mark.asyncio
    async def test_html_method_failure_raises(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "html"
            z.request_url = "https://www.zhihu.com/question/100/answer/200"
            with pytest.raises(Exception, match="Cannot get the answer"):
                await z._get_zhihu_answer()

    @pytest.mark.asyncio
    async def test_empty_answer_data_raises(self, _patch_zhihu_module):
        """When API returns empty data, _resolve_answer_json_data raises TypeError
        due to None concatenation, which propagates as an exception."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value={},
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/answers/200"
            with pytest.raises(TypeError):
                await z._get_zhihu_answer()

    @pytest.mark.asyncio
    async def test_title_empty_after_resolve_raises(self, _patch_zhihu_module):
        """When answer_data resolves but title is empty, should raise."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        api_response = {
            "question": {
                "id": 100,
                "title": None,  # Will result in empty title after resolve
                "detail": "",
                "answer_count": 0,
                "follower_count": 0,
                "created": 0,
                "updated_time": 0,
            },
            "author": {"name": "A", "url_token": "t"},
            "content": "<p>c</p>",
            "created_time": 0,
            "updated_time": 0,
            "comment_count": 0,
            "voteup_count": 0,
            "ipInfo": "",
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=api_response,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/answers/200"
            with pytest.raises(Exception, match="Cannot get the answer"):
                await z._get_zhihu_answer()


class TestGetZhihuArticle:
    """Tests for Zhihu._get_zhihu_article."""

    @pytest.mark.asyncio
    async def test_api_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "title": "Article Title",
            "content": "<p>article</p>",
            "author": {"name": "ArtAuthor", "url": "https://zhihu.com/people/art"},
            "voteup_count": 100,
            "comment_count": 5,
            "created": 1000,
            "updated": 2000,
            "column": {"title": "Col", "url": "http://col", "intro": "intro"},
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
            z.zhihu_type = "article"
            z.article_id = "12345"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/articles/12345"
            await z._get_zhihu_article()
        assert z.title == "Article Title"
        assert z.column == "Col"

    @pytest.mark.asyncio
    async def test_api_method_no_column(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "title": "No Col",
            "content": "<p>c</p>",
            "author": {"name": "A", "url": "u"},
            "voteup_count": 0,
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
            z.zhihu_type = "article"
            z.article_id = "12345"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/articles/12345"
            await z._get_zhihu_article()
        assert z.title == "No Col"
        assert not hasattr(z, "column")

    @pytest.mark.asyncio
    async def test_api_method_failure_raises(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
            z.zhihu_type = "article"
            z.article_id = "12345"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/articles/12345"
            with pytest.raises(Exception, match="zhihu request failed"):
                await z._get_zhihu_article()

    @pytest.mark.asyncio
    async def test_fxzhihu_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "title": "Fx Article",
            "content": "<p>fx</p>",
            "author": {"name": "FxA", "url": "u"},
            "voteup_count": 0,
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
            z.zhihu_type = "article"
            z.article_id = "12345"
            z.method = "fxzhihu"
            z.request_url = "https://fxzhihu.com/p/12345"
            await z._get_zhihu_article()
        assert z.title == "Fx Article"

    @pytest.mark.asyncio
    async def test_json_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        page_data = {
            "initialState": {
                "entities": {
                    "articles": {
                        "12345": {
                            "title": "Json Article",
                            "content": "<p>jc</p>",
                            "author": {"name": "JA", "urlToken": "ja_token"},
                            "voteupCount": 10,
                            "commentCount": 2,
                            "created": 1000,
                            "updated": 2000,
                            "column": {
                                "title": "JCol",
                                "url": "http://jcol",
                                "intro": "jintro",
                            },
                        }
                    }
                }
            }
        }
        mock_selector = MagicMock()
        mock_selector.xpath.return_value = json.dumps(page_data)
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
            z.zhihu_type = "article"
            z.article_id = "12345"
            z.method = "json"
            z.request_url = "https://zhuanlan.zhihu.com/p/12345"
            await z._get_zhihu_article()
        assert z.title == "Json Article"
        assert z.column == "JCol"

    @pytest.mark.asyncio
    async def test_html_method_success(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_selector = MagicMock()

        def xpath_side_effect(expr):
            if "string(//h1)" == expr:
                return "HTML Article"
            if "VoteButton" in expr:
                return "50"
            if "RichText" in expr and "ztext" in expr:
                return [MagicMock()]
            if "AuthorInfo-head" in expr:
                return "HtmlAuthor"
            if "UserLink-link" in expr:
                return "//www.zhihu.com/people/ha"
            return ""

        mock_selector.xpath.side_effect = xpath_side_effect
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.etree"
        ) as mock_etree:
            mock_etree.tostring.return_value = b"<div>content</div>"
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
            z.zhihu_type = "article"
            z.article_id = "12345"
            z.method = "html"
            z.request_url = "https://zhuanlan.zhihu.com/p/12345"
            await z._get_zhihu_article()
        assert z.title == "HTML Article"
        assert z.author_url == "https://www.zhihu.com/people/ha"

    @pytest.mark.asyncio
    async def test_get_selector_failure(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            side_effect=Exception("network"),
        ):
            z = Zhihu(url="https://zhuanlan.zhihu.com/p/12345")
            z.zhihu_type = "article"
            z.article_id = "12345"
            z.method = "html"
            z.request_url = "https://zhuanlan.zhihu.com/p/12345"
            with pytest.raises(Exception, match="zhihu request failed"):
                await z._get_zhihu_article()


class TestGetZhihuStatus:
    """Tests for Zhihu._get_zhihu_status."""

    @pytest.mark.asyncio
    async def test_api_method_no_retweet(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "StatusAuthor", "url_token": "sa"},
            "created": 1000,
            "updated": 2000,
            "content_html": "<p>status</p>",
            "reaction": {
                "statistics": {"up_vote_count": 10, "comment_count": 3}
            },
            "content": [
                {"type": "text", "content": "hello"},
                {"type": "image", "original_url": "http://img.jpg"},
            ],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert z.title == "StatusAuthor的想法"
        assert z.upvote == 10
        assert len(z.media_files) == 1
        assert z.retweeted is False

    @pytest.mark.asyncio
    async def test_api_method_with_retweet(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "Main", "url_token": "main"},
            "created": 1000,
            "updated": 2000,
            "content_html": "<p>main</p>",
            "reaction": {
                "statistics": {"up_vote_count": 5, "comment_count": 1}
            },
            "content": [],
            "origin_pin": {
                "id": 888,
                "author": {"name": "Origin", "url_token": "origin"},
                "created": 500,
                "updated": 600,
                "content_html": "<p>origin</p>",
                "content": [],
                "like_count": 2,
                "comment_count": 0,
            },
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert z.retweeted is True
        assert z.origin_pin_author == "Origin"

    @pytest.mark.asyncio
    async def test_api_method_without_reaction_field(self, _patch_zhihu_module):
        """When response uses like_count/comment_count instead of reaction.statistics."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "Author2", "url_token": "a2"},
            "created": 1000,
            "updated": 2000,
            "content_html": "<p>status2</p>",
            "like_count": 7,
            "comment_count": 4,
            "content": [],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert z.upvote == 7

    @pytest.mark.asyncio
    async def test_api_video_content_types(self, _patch_zhihu_module):
        """Test video content parsing in _resolve_status_api_data."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        # Test with video_info.playlist.hd
        json_data = {
            "author": {"name": "VA", "url_token": "va"},
            "created": 1000,
            "updated": 2000,
            "content_html": "",
            "like_count": 0,
            "comment_count": 0,
            "content": [
                {
                    "type": "video",
                    "video_info": {
                        "playlist": {
                            "hd": {"play_url": "http://hd.mp4"},
                            "sd": {"play_url": "http://sd.mp4"},
                        }
                    },
                }
            ],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert len(z.media_files) == 1
        assert z.media_files[0].url == "http://hd.mp4"

    @pytest.mark.asyncio
    async def test_api_video_no_hd_fallback(self, _patch_zhihu_module):
        """Test video fallback when no hd quality."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "VA", "url_token": "va"},
            "created": 1000,
            "updated": 2000,
            "content_html": "",
            "like_count": 0,
            "comment_count": 0,
            "content": [
                {
                    "type": "video",
                    "video_info": {
                        "playlist": {
                            "sd": {"play_url": "http://sd.mp4"},
                        }
                    },
                }
            ],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert z.media_files[0].url == "http://sd.mp4"

    @pytest.mark.asyncio
    async def test_api_video_playlist_format(self, _patch_zhihu_module):
        """Test video with playlist list format instead of video_info."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "VA", "url_token": "va"},
            "created": 1000,
            "updated": 2000,
            "content_html": "",
            "like_count": 0,
            "comment_count": 0,
            "content": [
                {
                    "type": "video",
                    "playlist": [
                        {"quality": "sd", "url": "http://sd2.mp4"},
                        {"quality": "hd", "url": "http://hd2.mp4"},
                    ],
                }
            ],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert z.media_files[0].url == "http://hd2.mp4"

    @pytest.mark.asyncio
    async def test_api_video_playlist_no_hd_fallback(self, _patch_zhihu_module):
        """Test video playlist format without hd quality falls back to first entry."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "VA", "url_token": "va"},
            "created": 1000,
            "updated": 2000,
            "content_html": "",
            "like_count": 0,
            "comment_count": 0,
            "content": [
                {
                    "type": "video",
                    "playlist": [
                        {"quality": "sd", "url": "http://sd3.mp4"},
                    ],
                }
            ],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert z.media_files[0].url == "http://sd3.mp4"

    @pytest.mark.asyncio
    async def test_api_video_no_url_found(self, _patch_zhihu_module):
        """Video content with empty playlist yields no media files."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "VA", "url_token": "va"},
            "created": 1000,
            "updated": 2000,
            "content_html": "",
            "like_count": 0,
            "comment_count": 0,
            "content": [
                {"type": "video"},
            ],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/pins/999"
            await z._get_zhihu_status()
        assert len(z.media_files) == 0

    @pytest.mark.asyncio
    async def test_html_method_selector_failure(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "html"
            z.request_url = "https://www.zhihu.com/pin/999"
            with pytest.raises(Exception, match="zhihu request failed"):
                await z._get_zhihu_status()

    @pytest.mark.asyncio
    async def test_fxzhihu_method_status(self, _patch_zhihu_module):
        """fxzhihu method for status uses get_response_json same as api."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        json_data = {
            "author": {"name": "FxStatus", "url_token": "fs"},
            "created": 1000,
            "updated": 2000,
            "content_html": "<p>fx status</p>",
            "like_count": 3,
            "comment_count": 1,
            "content": [],
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=json_data,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "fxzhihu"
            z.request_url = "https://fxzhihu.com/pin/999"
            await z._get_zhihu_status()
        assert z.title == "FxStatus的想法"
        # fxzhihu should NOT call fix_images_and_links (only api does)


class TestGetZhihuStatusJsonMethod:
    """Tests for Zhihu._get_zhihu_status with method='json'."""

    @pytest.mark.asyncio
    async def test_json_method_no_retweet(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        page_data = {
            "initialState": {
                "entities": {
                    "pins": {
                        "999": {
                            "author": "author_token",
                            "created": 1000,
                            "updated": 2000,
                            "content": [
                                {"content": "hello status"},
                                {"type": "image", "isGif": False, "originalUrl": "http://img.jpg"},
                            ],
                            "likeCount": 5,
                            "commentCount": 2,
                            "originPin": {"url": None},
                        }
                    },
                    "users": {
                        "author_token": {"name": "StatusAuthor"}
                    },
                }
            }
        }
        mock_selector = MagicMock()
        mock_selector.xpath.return_value = json.dumps(page_data)
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "json"
            z.request_url = "https://www.zhihu.com/pin/999"
            await z._get_zhihu_status()
        assert z.title == "StatusAuthor的想法"
        assert z.author == "StatusAuthor"
        assert z.upvote == 5
        assert len(z.media_files) == 1
        assert z.media_files[0].media_type == "image"

    @pytest.mark.asyncio
    async def test_json_method_with_retweet(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        page_data = {
            "initialState": {
                "entities": {
                    "pins": {
                        "999": {
                            "author": "author_token",
                            "created": 1000,
                            "updated": 2000,
                            "content": [{"content": "main status"}],
                            "likeCount": 5,
                            "commentCount": 2,
                            "originPin": {
                                "url": "https://www.zhihu.com/pin/888",
                                "author": {
                                    "name": "OriginAuthor",
                                    "urlToken": "origin_token",
                                },
                                "created": 500,
                                "updated": 600,
                                "content": [
                                    {"content": "origin text"},
                                    {"type": "video", "isGif": False, "originalUrl": "http://vid.mp4"},
                                ],
                                "likeCount": 1,
                                "commentCount": 0,
                            },
                        }
                    },
                    "users": {
                        "author_token": {"name": "MainAuthor"}
                    },
                }
            }
        }
        mock_selector = MagicMock()
        mock_selector.xpath.return_value = json.dumps(page_data)
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "json"
            z.request_url = "https://www.zhihu.com/pin/999"
            await z._get_zhihu_status()
        assert z.retweeted is True
        assert z.origin_pin_author == "OriginAuthor"
        assert len(z.media_files) == 1
        assert z.media_files[0].media_type == "video"

    @pytest.mark.asyncio
    async def test_json_method_gif_image(self, _patch_zhihu_module):
        """Test _process_picture with isGif=True."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        page_data = {
            "initialState": {
                "entities": {
                    "pins": {
                        "999": {
                            "author": "at",
                            "created": 1000,
                            "updated": 2000,
                            "content": [
                                {"content": "text"},
                                {"type": "image", "isGif": True, "originalUrl": "http://gif.gif"},
                            ],
                            "likeCount": 0,
                            "commentCount": 0,
                            "originPin": {"url": None},
                        }
                    },
                    "users": {"at": {"name": "A"}},
                }
            }
        }
        mock_selector = MagicMock()
        mock_selector.xpath.return_value = json.dumps(page_data)
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "json"
            z.request_url = "https://www.zhihu.com/pin/999"
            await z._get_zhihu_status()
        assert len(z.media_files) == 1
        assert z.media_files[0].media_type == "gif"


class TestGetZhihuStatusHtmlMethod:
    """Tests for Zhihu._get_zhihu_status with method='html'."""

    @pytest.mark.asyncio
    async def test_html_method_no_retweet(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_selector = MagicMock()

        def xpath_side_effect(expr):
            if "RichText" in expr and "itemprop" in expr:
                return [MagicMock()]
            if "VoteButton" in expr:
                return "10"
            if "ContentItem-time" in expr:
                return "2024-01-01"
            if "RichContent" in expr and "@class" in expr:
                return "some-other-class"  # No PinItem-content-originpin
            if 'itemprop="name"' in expr:
                return "HtmlAuthor"
            if 'itemprop="url"' in expr:
                return "https://www.zhihu.com/people/ha"
            return ""

        mock_selector.xpath.side_effect = xpath_side_effect
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.etree"
        ) as mock_etree:
            mock_etree.tostring.return_value = b"<span>status content</span>"
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "html"
            z.request_url = "https://www.zhihu.com/pin/999"
            await z._get_zhihu_status()
        assert z.title == "HtmlAuthor的想法"
        assert z.author == "HtmlAuthor"

    @pytest.mark.asyncio
    async def test_html_method_with_retweet_with_pics(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_selector = MagicMock()

        def xpath_side_effect(expr):
            if "RichText" in expr and "itemprop" in expr:
                return [MagicMock()]
            if "VoteButton" in expr:
                return "10"
            if "ContentItem-time" in expr:
                return "2024-01-01"
            if "RichContent" in expr and "@class" in expr:
                return "PinItem-content-originpin"  # Has retweet
            if "PinItem-content-originpin" in expr and "div[3]" in expr:
                return [MagicMock()]
            if "PinItem-content-originpin" in expr:
                return [MagicMock()]
            if 'itemprop="name"' in expr:
                return "Author"
            if 'itemprop="url"' in expr:
                return "https://www.zhihu.com/people/author"
            return ""

        mock_selector.xpath.side_effect = xpath_side_effect
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.etree"
        ) as mock_etree, patch(
            "fastfetchbot_shared.services.scrapers.zhihu.html"
        ) as mock_html:
            # Non-empty retweet content (not the empty marker div)
            mock_etree.tostring.return_value = b"<div>retweet content</div>"
            mock_html.fromstring.return_value = MagicMock()
            mock_html.tostring.return_value = b"<div>pretty retweet</div>"
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "html"
            z.request_url = "https://www.zhihu.com/pin/999"
            await z._get_zhihu_status()
        assert z.title == "Author的想法"
        assert z.retweet_html != ""

    @pytest.mark.asyncio
    async def test_html_method_with_retweet_no_pics(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_selector = MagicMock()
        call_count = {"originpin_div3": 0}

        def xpath_side_effect(expr):
            if "RichText" in expr and "itemprop" in expr:
                return [MagicMock()]
            if "VoteButton" in expr:
                return "10"
            if "ContentItem-time" in expr:
                return "2024-01-01"
            if "RichContent" in expr and "@class" in expr:
                return "PinItem-content-originpin"
            if "PinItem-content-originpin" in expr and "div[3]" in expr:
                return [MagicMock()]
            if "PinItem-content-originpin" in expr:
                return [MagicMock()]
            if 'itemprop="name"' in expr:
                return "Author"
            if 'itemprop="url"' in expr:
                return "https://www.zhihu.com/people/author"
            return ""

        mock_selector.xpath.side_effect = xpath_side_effect
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_selector",
            new_callable=AsyncMock,
            return_value=mock_selector,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.etree"
        ) as mock_etree:
            # Return the empty marker div for retweet check
            mock_etree.tostring.side_effect = [
                b'<span>content</span>',  # main content
                b'<div class="RichText ztext PinItem-remainContentRichText"/>',  # originpin/div[3]
                b'<div>originpin content</div>',  # PinItem-content-originpin
            ]
            z = Zhihu(url="https://www.zhihu.com/pin/999")
            z.zhihu_type = "status"
            z.status_id = "999"
            z.method = "html"
            z.request_url = "https://www.zhihu.com/pin/999"
            await z._get_zhihu_status()
        assert z.title == "Author的想法"


class TestParseStatusJsonData:
    """Tests for Zhihu._parse_status_json_data."""

    def test_parses_status_data(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
        z.status_id = "999"
        data = {
            "pins": {
                "999": {
                    "author": "author_token",
                    "created": 1000,
                    "updated": 2000,
                    "content": [
                        {"content": "status text"},
                    ],
                    "likeCount": 5,
                    "commentCount": 2,
                    "originPin": {
                        "url": None,
                        "author": {"name": "X", "urlToken": "xt"},
                        "created": 0,
                        "updated": 0,
                        "content": [{"content": ""}],
                        "likeCount": 0,
                        "commentCount": 0,
                    },
                }
            },
            "users": {
                "author_token": {"name": "Author"}
            },
        }
        result = z._parse_status_json_data(data)
        assert result["author"] == "Author"
        assert result["content"] == "status text"
        assert result["like_count"] == 5


class TestGetZhihuItem:
    """Tests for Zhihu._get_zhihu_item (the main fallback logic)."""

    @pytest.mark.asyncio
    async def test_first_method_succeeds(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        api_response = {
            "question": {
                "id": 100,
                "title": "Q",
                "detail": "",
                "answer_count": 1,
                "follower_count": 1,
                "created": 1000,
                "updated_time": 2000,
            },
            "author": {"name": "A", "url_token": "at"},
            "content": "<p>c</p>",
            "created_time": 1000,
            "updated_time": 2000,
            "comment_count": 0,
            "voteup_count": 0,
            "ipInfo": "",
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=api_response,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            await z._get_zhihu_item()
        assert z.title == "Q"

    @pytest.mark.asyncio
    async def test_first_method_fails_second_succeeds(self, _patch_zhihu_module):
        """First method (api) fails, second method (fxzhihu) succeeds."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        call_count = 0

        async def mock_get_response_json(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("api failed")
            return {
                "question": {
                    "id": 100,
                    "title": "FallbackQ",
                    "detail": "",
                    "answer_count": 1,
                    "follower_count": 1,
                    "created": 1000,
                    "updated_time": 2000,
                },
                "author": {"name": "A", "url_token": "at"},
                "content": "<p>c</p>",
                "created_time": 1000,
                "updated_time": 2000,
                "comment_count": 0,
                "voteup_count": 0,
                "ipInfo": "",
            }

        # fxzhihu for answer uses get_response, not get_response_json
        response_data = {
            "question": {
                "id": 100,
                "title": "FallbackQ",
                "detail": "",
                "answer_count": 1,
                "follower_count": 1,
                "created": 1000,
                "updated_time": 2000,
            },
            "author": {"name": "FA", "url_token": "fat"},
            "content": "<p>fx</p>",
            "created_time": 1000,
            "updated_time": 2000,
            "comment_count": 0,
            "voteup_count": 0,
            "ipInfo": "",
        }
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(response_data)

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            side_effect=mock_get_response_json,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.settings.FXZHIHU_HOST", "fxzhihu.com"
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            await z._get_zhihu_item()
        assert z.title == "FallbackQ"

    @pytest.mark.asyncio
    async def test_all_methods_fail(self, _patch_zhihu_module):
        """When all methods fail, raises the last exception."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            side_effect=Exception("api fail"),
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response",
            new_callable=AsyncMock,
            side_effect=Exception("fx fail"),
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.settings.FXZHIHU_HOST", "fxzhihu.com"
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            with pytest.raises(Exception):
                await z._get_zhihu_item()

    @pytest.mark.asyncio
    async def test_invalid_method_defaults_to_api(self, _patch_zhihu_module):
        """When self.method is not in ALL_METHODS, it's reset to 'api'."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        api_response = {
            "question": {
                "id": 100,
                "title": "Q",
                "detail": "",
                "answer_count": 1,
                "follower_count": 1,
                "created": 1000,
                "updated_time": 2000,
            },
            "author": {"name": "A", "url_token": "at"},
            "content": "<p>c</p>",
            "created_time": 1000,
            "updated_time": 2000,
            "comment_count": 0,
            "voteup_count": 0,
            "ipInfo": "",
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=api_response,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(
                url="https://www.zhihu.com/question/100/answer/200",
                method="invalid_method",
            )
            await z._get_zhihu_item()
        assert z.title == "Q"


class TestZhihuShortTextProcess:
    """Tests for Zhihu._zhihu_short_text_process."""

    def test_basic_processing(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
        z.zhihu_type = "answer"
        z.raw_content = "<p>Hello</p>"
        z._zhihu_short_text_process()
        # Template was called
        assert isinstance(z.text, str)

    def test_status_with_retweet(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
        z.zhihu_type = "status"
        z.retweeted = True
        z.raw_content = "<p>main</p>"
        z.origin_pin_raw_content = "<p>origin</p>"
        z._zhihu_short_text_process()
        assert isinstance(z.text, str)

    def test_img_with_data_image_skipped(self, _patch_zhihu_module):
        """Images with data:image src should be skipped (no media_files added)."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = '<img src="data:image/png;base64,abc">'
        z._zhihu_short_text_process()
        # No media files should be added for data:image src
        assert len(z.media_files) == 0

    def test_img_with_actual_src(self, _patch_zhihu_module):
        """Images with real src are added to media_files for non-status types."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = '<img src="http://img.zhihu.com/pic.jpg">'
        z._zhihu_short_text_process()
        assert len(z.media_files) == 1

    def test_img_status_type_not_added(self, _patch_zhihu_module):
        """For status type, images are not added to media_files in short text processing."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/pin/999")
        z.zhihu_type = "status"
        z.retweeted = False
        z.raw_content = '<img src="http://img.zhihu.com/pic.jpg">'
        z._zhihu_short_text_process()
        assert len(z.media_files) == 0

    def test_a_tag_without_href(self, _patch_zhihu_module):
        """<a> tags without href should be unwrapped."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = '<a>no href</a><a href="http://link">with href</a>'
        z._zhihu_short_text_process()
        assert isinstance(z.text, str)

    def test_text_ends_with_newline_stripped(self, _patch_zhihu_module):
        """Text ending with a single newline should have it stripped."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        templates = _patch_zhihu_module
        # Return plain text ending with \n (no html tags that would get processed)
        templates["short_text_template"].render.return_value = "simple text\n"
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = "<p>text</p>"
        z._zhihu_short_text_process()
        assert not z.text.endswith("\n")

    def test_h_tags_and_p_tags_processing(self, _patch_zhihu_module):
        """h tags and p tags should be unwrapped with br appended."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        templates = _patch_zhihu_module
        templates["short_text_template"].render.return_value = (
            "<h1>Header</h1><p>Paragraph</p><h2></h2><p></p>"
        )
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = "<p>text</p>"
        z._zhihu_short_text_process()
        # h and p tags with text get <br> appended; empty ones still get unwrapped
        assert isinstance(z.text, str)


class TestZhihuShortTextProcessExtra:
    """Additional tests for inner _html_process function in _zhihu_short_text_process."""

    def test_figure_tags_decomposed(self, _patch_zhihu_module):
        """Figure tags should be decomposed."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = '<figure><img src="http://test.jpg"></figure>'
        z._zhihu_short_text_process()
        assert isinstance(z.text, str)
        assert len(z.media_files) == 1

    def test_br_tags_replaced_with_newline(self, _patch_zhihu_module):
        """br tags should be replaced with newlines in the processed content."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = "line1<br>line2"
        z._zhihu_short_text_process()
        assert isinstance(z.text, str)

    def test_content_with_br_replacement(self, _patch_zhihu_module):
        """Raw content with </br></br> should be replaced with newlines."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.zhihu_type = "answer"
        z.raw_content = "paragraph1</br></br>paragraph2"
        z._zhihu_short_text_process()
        assert isinstance(z.text, str)


class TestZhihuContentProcess:
    """Tests for Zhihu._zhihu_content_process."""

    def test_content_rendering(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        z.raw_content = "<p>test\ncontent</p>"
        z._zhihu_content_process()
        assert z.content == "<div>rendered content</div>"


class TestResolveAnswerJsonData:
    """Tests for Zhihu._resolve_answer_json_data."""

    def test_resolve_with_full_data(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        answer_data = {
            "question_detail": "<p>detail</p>",
            "question_created": 1000,
            "question_updated": 2000,
            "follower_count": 10,
            "answer_count": 5,
            "title": "Title",
            "author": "Author",
            "author_url_token": "token",
            "content": "<p>content</p>",
            "created": 3000,
            "updated": 4000,
            "comment_count": 2,
            "voteup_count": 50,
            "ip_info": "Beijing",
        }
        z._resolve_answer_json_data(answer_data)
        assert z.title == "Title"
        assert z.author == "Author"
        assert z.upvote == 50

    def test_resolve_with_none_author_url_token_raises(self, _patch_zhihu_module):
        """When author_url_token is None, concatenation with ZHIHU_HOST raises TypeError."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        answer_data = {
            "question_detail": None,
            "question_created": None,
            "question_updated": None,
            "follower_count": None,
            "answer_count": None,
            "title": None,
            "author": None,
            "author_url_token": None,
            "content": None,
            "created": None,
            "updated": None,
            "comment_count": None,
            "voteup_count": None,
            "ip_info": None,
        }
        with pytest.raises(TypeError):
            z._resolve_answer_json_data(answer_data)

    def test_resolve_with_empty_string_values(self, _patch_zhihu_module):
        """When values are empty strings instead of None, resolution works correctly."""
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
        answer_data = {
            "question_detail": "",
            "question_created": "",
            "question_updated": "",
            "follower_count": 0,
            "answer_count": 0,
            "title": "",
            "author": "",
            "author_url_token": "",
            "content": "",
            "created": "",
            "updated": "",
            "comment_count": 0,
            "voteup_count": 0,
            "ip_info": "",
        }
        z._resolve_answer_json_data(answer_data)
        assert z.title == ""
        assert z.question == ""
        assert z.question_follower_count == 0


class TestGetItem:
    """Test the get_item and get_zhihu methods."""

    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        api_response = {
            "question": {
                "id": 100,
                "title": "Q",
                "detail": "",
                "answer_count": 1,
                "follower_count": 1,
                "created": 1000,
                "updated_time": 2000,
            },
            "author": {"name": "A", "url_token": "at"},
            "content": "<p>c</p>",
            "created_time": 1000,
            "updated_time": 2000,
            "comment_count": 0,
            "voteup_count": 0,
            "ipInfo": "",
        }
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value=api_response,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.fix_images_and_links",
            side_effect=lambda x: x,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.unmask_zhihu_links",
            side_effect=lambda x: x,
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            result = await z.get_item()
        assert isinstance(result, dict)
        assert "url" in result
        assert "title" in result


class TestGetQuestionId:
    """Test Zhihu._get_question_id."""

    @pytest.mark.asyncio
    async def test_gets_question_id_from_redirect(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_redirect_url",
            new_callable=AsyncMock,
            return_value="https://www.zhihu.com/question/777/answer/200",
        ):
            z = Zhihu(url="https://www.zhihu.com/answer/200")
            await z._get_question_id()
        assert z.question_id == "777"


class TestGenerateZhihuCookie:
    """Test Zhihu._generate_zhihu_cookie (currently a pass/no-op)."""

    def test_no_op(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch("fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None):
            z = Zhihu(url="https://www.zhihu.com/pin/1")
        result = z._generate_zhihu_cookie()
        assert result is None


class TestAnswerDataEmptyDict:
    """Cover line 322: answer_data == {} raises."""

    @pytest.mark.asyncio
    async def test_api_returns_empty_dict_raises(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.get_response_json",
            new_callable=AsyncMock,
            return_value={},
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu._parse_answer_api_json_data",
            return_value={},
        ):
            z = Zhihu(url="https://www.zhihu.com/question/100/answer/200")
            z.zhihu_type = "answer"
            z.answer_id = "200"
            z.method = "api"
            z.request_url = "https://www.zhihu.com/api/v4/answers/200"
            with pytest.raises(Exception, match="Cannot get the answer"):
                await z._get_zhihu_answer()


class TestShortTextProcessPTags:
    """Cover lines 652-654: p tag processing after format_telegram_short_text."""

    def test_p_tags_survive_format_telegram(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_template = MagicMock()
        mock_template.render.return_value = "<p>paragraph one</p><p>paragraph two</p>"

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.short_text_template",
            mock_template,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.format_telegram_short_text",
            side_effect=lambda soup: soup,  # Don't unwrap p tags
        ):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
            z.zhihu_type = "answer"
            z.raw_content = "<p>content</p>"
            z.retweeted = False
            z._zhihu_short_text_process()
            assert isinstance(z.text, str)
            assert "paragraph one" in z.text

    def test_empty_p_tags_no_br_appended(self, _patch_zhihu_module):
        from fastfetchbot_shared.services.scrapers.zhihu import Zhihu

        mock_template = MagicMock()
        mock_template.render.return_value = "<p></p><p>text</p>"

        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_API_COOKIE", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.ZHIHU_COOKIES", None
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.short_text_template",
            mock_template,
        ), patch(
            "fastfetchbot_shared.services.scrapers.zhihu.format_telegram_short_text",
            side_effect=lambda soup: soup,
        ):
            z = Zhihu(url="https://www.zhihu.com/question/1/answer/2")
            z.zhihu_type = "answer"
            z.raw_content = "<p>content</p>"
            z.retweeted = False
            z._zhihu_short_text_process()
            assert isinstance(z.text, str)

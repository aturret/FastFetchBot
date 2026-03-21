"""Tests for packages/shared/fastfetchbot_shared/services/scrapers/general/base.py"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.models.metadata_item import MessageType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_general_text_limit(self):
        from fastfetchbot_shared.services.scrapers.general.base import GENERAL_TEXT_LIMIT
        assert GENERAL_TEXT_LIMIT == 800

    def test_default_openai_model(self):
        from fastfetchbot_shared.services.scrapers.general.base import DEFAULT_OPENAI_MODEL
        assert DEFAULT_OPENAI_MODEL == "gpt-5-nano"


# ---------------------------------------------------------------------------
# BaseGeneralScraper (abstract – just verify it cannot be instantiated)
# ---------------------------------------------------------------------------


class TestBaseGeneralScraper:
    def test_has_abstract_method(self):
        """BaseGeneralScraper declares get_processor_by_url as abstract."""
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralScraper
        assert hasattr(BaseGeneralScraper, "get_processor_by_url")
        assert getattr(
            BaseGeneralScraper.get_processor_by_url, "__isabstractmethod__", False
        )

    @pytest.mark.asyncio
    async def test_abstract_get_processor_by_url_pass(self):
        """Execute the abstract pass body for coverage."""
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralScraper

        class ConcreteScraper(BaseGeneralScraper):
            async def get_processor_by_url(self, url):
                return await super().get_processor_by_url(url)

        s = ConcreteScraper()
        result = await s.get_processor_by_url("https://example.com")
        assert result is None


# ---------------------------------------------------------------------------
# BaseGeneralDataProcessor
# ---------------------------------------------------------------------------


class _ConcreteProcessor:
    """Minimal concrete subclass for testing the base class logic."""
    _get_page_called = False

    async def _get_page_content(self):
        self._get_page_called = True


def _make_processor(url="https://example.com/page"):
    """Create a concrete processor that inherits BaseGeneralDataProcessor."""
    from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor

    class ConcreteProcessor(BaseGeneralDataProcessor):
        _get_page_called = False

        async def _get_page_content(self):
            self._get_page_called = True

    return ConcreteProcessor(url)


class TestBaseGeneralDataProcessorInit:
    def test_init_sets_fields(self):
        url = "https://example.com/page"
        proc = _make_processor(url)
        assert proc.url == url
        assert proc._data == {}
        assert proc.url_parser.netloc == "example.com"
        expected_id = hashlib.md5(url.encode()).hexdigest()[:16]
        assert proc.id == expected_id
        assert proc.scraper_type == "base"


class TestBaseGeneralDataProcessorGetItem:
    @pytest.mark.asyncio
    async def test_get_item_calls_process_data(self):
        proc = _make_processor("https://example.com/page")
        # Populate _data so GeneralItem.from_dict works
        proc._data = {
            "id": "abc",
            "category": "other",
            "url": "https://example.com/page",
            "title": "Title",
            "author": "Author",
            "author_url": "https://example.com",
            "text": "hello",
            "content": "<p>hello</p>",
            "raw_content": "hello",
            "media_files": [],
            "message_type": "short",
            "telegraph_url": "",
            "scraper_type": "base",
        }
        # Override process_data to avoid real scraping
        proc.process_data = AsyncMock()
        result = await proc.get_item()
        proc.process_data.assert_awaited_once()
        assert isinstance(result, dict)
        assert result["title"] == "Title"

    @pytest.mark.asyncio
    async def test_process_data_calls_get_page_content(self):
        proc = _make_processor("https://example.com/page")
        await proc.process_data()
        assert proc._get_page_called

    @pytest.mark.asyncio
    async def test_abstract_get_page_content_pass(self):
        """Execute the abstract _get_page_content pass body for coverage."""
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor

        class DirectProcessor(BaseGeneralDataProcessor):
            async def _get_page_content(self):
                await super()._get_page_content()

        proc = DirectProcessor("https://example.com/page")
        await proc._get_page_content()  # should just pass


# ---------------------------------------------------------------------------
# _build_item_data
# ---------------------------------------------------------------------------


class TestBuildItemData:
    @pytest.mark.asyncio
    @patch(
        "fastfetchbot_shared.services.scrapers.general.base.BaseGeneralDataProcessor.parsing_article_body_by_llm",
        new_callable=AsyncMock,
        return_value="<p>cleaned</p>",
    )
    async def test_with_html_content_and_og_image(self, mock_llm):
        proc = _make_processor("https://example.com/page")
        await proc._build_item_data(
            title="My Title",
            author="Author",
            description="desc",
            markdown_content="md content",
            html_content="<p>raw html</p>",
            og_image="https://img.example.com/pic.jpg",
        )
        data = proc._data
        assert data["title"] == "My Title"
        assert data["author"] == "Author"
        assert data["author_url"] == "https://example.com"
        assert data["text"] == "desc"
        assert len(data["media_files"]) == 1
        assert data["media_files"][0]["url"] == "https://img.example.com/pic.jpg"
        mock_llm.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "fastfetchbot_shared.services.scrapers.general.base.BaseGeneralDataProcessor.parsing_article_body_by_llm",
        new_callable=AsyncMock,
        return_value="<p>cleaned</p>",
    )
    async def test_without_og_image(self, mock_llm):
        proc = _make_processor("https://example.com/page")
        await proc._build_item_data(
            title="Title",
            author="A",
            description="d",
            markdown_content="md",
            html_content="<p>html</p>",
            og_image=None,
        )
        assert proc._data["media_files"] == []

    @pytest.mark.asyncio
    async def test_empty_title_and_author_fallback(self):
        proc = _make_processor("https://example.com/page")
        await proc._build_item_data(
            title="",
            author="",
            description="",
            markdown_content="md",
            html_content="",
            og_image=None,
        )
        data = proc._data
        assert data["title"] == "https://example.com/page"
        assert data["author"] == "example.com"

    @pytest.mark.asyncio
    async def test_no_html_content_uses_markdown(self):
        proc = _make_processor("https://example.com/page")
        await proc._build_item_data(
            title="T",
            author="A",
            description="",
            markdown_content="some markdown",
            html_content="",
            og_image=None,
        )
        data = proc._data
        # wrap_text_into_html wraps non-html text into <p> tags
        assert "<p>" in data["content"]

    @pytest.mark.asyncio
    @patch(
        "fastfetchbot_shared.services.scrapers.general.base.BaseGeneralDataProcessor.parsing_article_body_by_llm",
        new_callable=AsyncMock,
        return_value="<p>c</p>",
    )
    async def test_long_message_type(self, mock_llm):
        proc = _make_processor("https://example.com/page")
        long_html = "<p>" + "x" * 1000 + "</p>"
        await proc._build_item_data(
            title="T",
            author="A",
            description="d",
            markdown_content="",
            html_content=long_html,
            og_image=None,
        )
        # The LLM mock returns short content so message_type is SHORT
        assert proc._data["message_type"] == MessageType.SHORT

    @pytest.mark.asyncio
    @patch(
        "fastfetchbot_shared.services.scrapers.general.base.BaseGeneralDataProcessor.parsing_article_body_by_llm",
        new_callable=AsyncMock,
    )
    async def test_long_message_type_actual_long(self, mock_llm):
        long_text = "x" * 1000
        mock_llm.return_value = f"<p>{long_text}</p>"
        proc = _make_processor("https://example.com/page")
        await proc._build_item_data(
            title="T",
            author="A",
            description="d",
            markdown_content="",
            html_content=f"<p>{long_text}</p>",
            og_image=None,
        )
        assert proc._data["message_type"] == MessageType.LONG

    @pytest.mark.asyncio
    async def test_description_fallback_to_markdown_prefix(self):
        proc = _make_processor("https://example.com/page")
        await proc._build_item_data(
            title="T",
            author="A",
            description="",
            markdown_content="short md text",
            html_content="",
            og_image=None,
        )
        assert proc._data["text"] == "short md text"

    @pytest.mark.asyncio
    async def test_description_strips_html_tags(self):
        proc = _make_processor("https://example.com/page")
        await proc._build_item_data(
            title="T",
            author="A",
            description="<b>bold</b> text",
            markdown_content="",
            html_content="",
            og_image=None,
        )
        assert proc._data["text"] == "bold text"


# ---------------------------------------------------------------------------
# sanitize_html
# ---------------------------------------------------------------------------


class TestSanitizeHtml:
    def test_empty_string(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        assert BaseGeneralDataProcessor.sanitize_html("") == ""

    def test_none_returns_none(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        assert BaseGeneralDataProcessor.sanitize_html(None) is None

    def test_removes_doctype(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        html = "<!DOCTYPE html><p>Hello</p>"
        result = BaseGeneralDataProcessor.sanitize_html(html)
        assert "DOCTYPE" not in result
        assert "<p>Hello</p>" in result

    def test_removes_script_style(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        html = "<script>alert(1)</script><style>.x{}</style><p>text</p>"
        result = BaseGeneralDataProcessor.sanitize_html(html)
        assert "script" not in result
        assert "style" not in result
        assert "<p>text</p>" in result

    def test_removes_head_meta_link_noscript_iframe_svg_form_input_button(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        html = (
            "<head><title>t</title></head>"
            "<meta charset='utf-8'>"
            "<link rel='stylesheet'>"
            "<noscript>no js</noscript>"
            "<iframe src='x'></iframe>"
            "<svg><circle/></svg>"
            "<form><input><button>b</button></form>"
            "<p>keep</p>"
        )
        result = BaseGeneralDataProcessor.sanitize_html(html)
        assert "<p>keep</p>" in result
        for tag in ["head", "meta", "link", "noscript", "iframe", "svg", "form", "input", "button"]:
            assert f"<{tag}" not in result

    def test_unwraps_structural_tags(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        html = "<html><body><div><span>text</span></div></body></html>"
        result = BaseGeneralDataProcessor.sanitize_html(html)
        assert "text" in result
        for tag in ["html", "body", "div", "span"]:
            assert f"<{tag}" not in result

    def test_unwraps_semantic_layout_tags(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        html = (
            "<section><article><nav>n</nav><header>h</header>"
            "<footer>f</footer><main>m</main><aside>a</aside>"
            "<figure><figcaption>fc</figcaption></figure>"
            "<details><summary>s</summary></details>"
            "<dl><dt>term</dt><dd>def</dd></dl></article></section>"
        )
        result = BaseGeneralDataProcessor.sanitize_html(html)
        for tag in ["section", "article", "nav", "header", "footer", "main",
                     "aside", "figure", "figcaption", "details", "summary",
                     "dl", "dt", "dd"]:
            assert f"<{tag}" not in result
        # Text content preserved
        for text in ["n", "h", "f", "m", "a", "fc", "s", "term", "def"]:
            assert text in result

    def test_preserves_content_tags(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        html = (
            "<p>para</p><h1>h</h1><a href='#'>link</a><b>bold</b>"
            "<strong>strong</strong><i>italic</i><em>em</em><u>underline</u>"
            "<ul><li>item</li></ul><ol><li>num</li></ol>"
            "<blockquote>quote</blockquote><pre><code>code</code></pre>"
            "<img src='x.jpg'><br>"
            "<table><thead><tr><th>h</th></tr></thead><tbody><tr><td>d</td></tr></tbody></table>"
        )
        result = BaseGeneralDataProcessor.sanitize_html(html)
        for tag in ["p", "h1", "a", "b", "strong", "i", "em", "u",
                     "ul", "ol", "li", "blockquote", "pre", "code",
                     "img", "br", "table", "thead", "tbody", "tr", "th", "td"]:
            assert f"<{tag}" in result


# ---------------------------------------------------------------------------
# parsing_article_body_by_llm
# ---------------------------------------------------------------------------


class TestParsingArticleBodyByLlm:
    @pytest.mark.asyncio
    async def test_empty_input(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        result = await BaseGeneralDataProcessor.parsing_article_body_by_llm("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_none_input(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        result = await BaseGeneralDataProcessor.parsing_article_body_by_llm(None)
        assert result is None

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.base.OPENAI_API_KEY", None)
    async def test_no_api_key(self):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        result = await BaseGeneralDataProcessor.parsing_article_body_by_llm("<p>html</p>")
        assert result == "<p>html</p>"

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.base.OPENAI_API_KEY", "sk-test")
    @patch("fastfetchbot_shared.services.scrapers.general.base.AsyncOpenAI")
    async def test_success(self, mock_openai_cls):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "  <p>extracted</p>  "
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        result = await BaseGeneralDataProcessor.parsing_article_body_by_llm("<p>raw</p>")
        assert result == "<p>extracted</p>"
        mock_openai_cls.assert_called_once_with(api_key="sk-test")

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.base.OPENAI_API_KEY", "sk-test")
    @patch("fastfetchbot_shared.services.scrapers.general.base.AsyncOpenAI")
    async def test_empty_response(self, mock_openai_cls):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        result = await BaseGeneralDataProcessor.parsing_article_body_by_llm("<p>raw</p>")
        assert result == "<p>raw</p>"

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.base.OPENAI_API_KEY", "sk-test")
    @patch("fastfetchbot_shared.services.scrapers.general.base.AsyncOpenAI")
    async def test_exception(self, mock_openai_cls):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")

        result = await BaseGeneralDataProcessor.parsing_article_body_by_llm("<p>raw</p>")
        assert result == "<p>raw</p>"

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.base.OPENAI_API_KEY", "sk-test")
    @patch("fastfetchbot_shared.services.scrapers.general.base.AsyncOpenAI")
    async def test_truncates_long_content(self, mock_openai_cls):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "<p>ok</p>"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        long_html = "x" * 60000
        result = await BaseGeneralDataProcessor.parsing_article_body_by_llm(long_html)
        assert result == "<p>ok</p>"
        # Verify the content sent to OpenAI was truncated
        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        # The user message includes the prefix + truncated content
        assert len(user_msg) < 60000 + 200

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.general.base.OPENAI_API_KEY", "sk-test")
    @patch("fastfetchbot_shared.services.scrapers.general.base.AsyncOpenAI")
    async def test_short_content_not_truncated(self, mock_openai_cls):
        from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralDataProcessor
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "<p>ok</p>"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        short_html = "<p>short</p>"
        await BaseGeneralDataProcessor.parsing_article_body_by_llm(short_html)
        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert short_html in user_msg

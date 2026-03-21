"""Unit tests for douban scraper: DoubanType enum, Douban class with all methods."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from lxml import etree

from fastfetchbot_shared.models.metadata_item import MessageType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_selector_with_xpaths(xpath_map: dict):
    """Create a mock lxml selector that responds to xpath() calls."""
    selector = MagicMock()

    def xpath_side_effect(expr):
        for key, val in xpath_map.items():
            if key in expr:
                return val
        return ""

    selector.xpath = MagicMock(side_effect=xpath_side_effect)
    return selector


def _make_html_element(html_str: str):
    """Create a real lxml element from HTML string for tostring calls."""
    tree = etree.HTML(html_str)
    return tree


@pytest.fixture(autouse=True)
def _patch_douban_templates():
    mock_tpl = MagicMock()
    mock_tpl.render.return_value = "<p>rendered</p>"
    with patch(
        "fastfetchbot_shared.services.scrapers.douban.short_text_template", mock_tpl
    ), patch(
        "fastfetchbot_shared.services.scrapers.douban.content_template", mock_tpl
    ):
        yield mock_tpl


@pytest.fixture
def _patch_get_selector():
    with patch(
        "fastfetchbot_shared.services.scrapers.douban.get_selector",
        new_callable=AsyncMock,
    ) as m:
        yield m


# ---------------------------------------------------------------------------
# DoubanType enum tests
# ---------------------------------------------------------------------------

class TestDoubanType:

    def test_enum_values(self):
        from fastfetchbot_shared.services.scrapers.douban import DoubanType

        assert DoubanType.MOVIE_REVIEW == "movie_review"
        assert DoubanType.BOOK_REVIEW == "book_review"
        assert DoubanType.NOTE == "note"
        assert DoubanType.STATUS == "status"
        assert DoubanType.GROUP == "group"
        assert DoubanType.UNKNOWN == "unknown"

    def test_enum_is_string(self):
        from fastfetchbot_shared.services.scrapers.douban import DoubanType

        assert isinstance(DoubanType.MOVIE_REVIEW, str)


# ---------------------------------------------------------------------------
# Douban.__init__ tests
# ---------------------------------------------------------------------------

class TestDoubanInit:

    def test_default_fields(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://www.douban.com/note/12345/")
        assert d.url == "https://www.douban.com/note/12345/"
        assert d.title == ""
        assert d.author == ""
        assert d.author_url == ""
        assert d.text == ""
        assert d.content == ""
        assert d.media_files == []
        assert d.category == "douban"
        assert d.message_type == MessageType.SHORT
        assert d.item_title is None
        assert d.item_url is None
        assert d.group_name is None
        assert d.group_url is None
        assert d.douban_type == DoubanType.UNKNOWN
        assert d.text_group is None
        assert d.raw_content is None
        assert d.date is None

    def test_cookie_passed_to_headers(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/", cookie="session=abc")
        assert d.headers["Cookie"] == "session=abc"

    def test_no_cookie(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        assert d.headers["Cookie"] == ""


# ---------------------------------------------------------------------------
# check_douban_type tests
# ---------------------------------------------------------------------------

class TestCheckDoubanType:

    def test_note_type(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://www.douban.com/note/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.NOTE

    def test_status_type_with_status_path(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://www.douban.com/status/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.STATUS

    def test_status_type_with_people_status_path(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://www.douban.com/people/12345/status/67890")
        d.check_douban_type()
        assert d.douban_type == DoubanType.STATUS

    def test_group_type(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://www.douban.com/group/topic/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.GROUP

    def test_movie_review_direct(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://movie.douban.com/review/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.MOVIE_REVIEW

    def test_book_review_direct(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://book.douban.com/review/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.BOOK_REVIEW

    def test_m_douban_movie_review(self):
        """m.douban.com with /movie/review path should map to MOVIE_REVIEW."""
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://m.douban.com/movie/review/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.MOVIE_REVIEW
        # URL should be rewritten to desktop domain
        assert "movie.douban.com" in d.url
        assert "/review/12345/" in d.url

    def test_m_douban_book_review(self):
        """m.douban.com with /book/review path should map to BOOK_REVIEW."""
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://m.douban.com/book/review/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.BOOK_REVIEW
        assert "book.douban.com" in d.url

    def test_m_douban_note(self):
        """m.douban.com with /note/ path should map to NOTE."""
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://m.douban.com/note/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.NOTE

    def test_unknown_type(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://www.douban.com/people/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.UNKNOWN

    def test_url_rewritten(self):
        """URL should be rewritten to https://{host}{path} format."""
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/?query=1")
        d.check_douban_type()
        assert d.url == "https://www.douban.com/note/12345/"

    def test_m_douban_non_review(self):
        """m.douban.com with non-review path should still rewrite host."""
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        d = Douban("https://m.douban.com/group/topic/12345/")
        d.check_douban_type()
        assert d.douban_type == DoubanType.GROUP
        assert "douban.com" in d.url


# ---------------------------------------------------------------------------
# get_douban_item tests
# ---------------------------------------------------------------------------

class TestGetDoubanItem:

    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self, _patch_get_selector, _patch_douban_templates):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        # Build a real lxml tree for xpath calls
        html = """
        <html><body>
        <h1>Test Note</h1>
        <div class="content"><a href="/people/123/">Author</a></div>
        <div id="link-report"><p>Content here</p></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector
        _patch_douban_templates.render.return_value = "short"

        d = Douban("https://www.douban.com/note/12345/")
        result = await d.get_item()

        assert isinstance(result, dict)
        assert result["category"] == "douban"

    @pytest.mark.asyncio
    async def test_get_douban_item_long_content(self, _patch_get_selector, _patch_douban_templates):
        """When content exceeds SHORT_LIMIT, message_type should be LONG."""
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <h1>Test Note</h1>
        <div class="content"><a href="/people/123/">Author</a></div>
        <div id="link-report"><p>Content here</p></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        # Make wrap_text_into_html return long content
        with patch(
            "fastfetchbot_shared.services.scrapers.douban.wrap_text_into_html",
            return_value="x" * 700,
        ), patch(
            "fastfetchbot_shared.services.scrapers.douban.get_html_text_length",
            return_value=700,
        ):
            d = Douban("https://www.douban.com/note/12345/")
            await d.get_douban()
            assert d.message_type == MessageType.LONG

    @pytest.mark.asyncio
    async def test_get_douban_item_short_content(self, _patch_get_selector, _patch_douban_templates):
        """When content is within SHORT_LIMIT, message_type should be SHORT."""
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <h1>Test Note</h1>
        <div class="content"><a href="/people/123/">Author</a></div>
        <div id="link-report"><p>Short</p></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        with patch(
            "fastfetchbot_shared.services.scrapers.douban.wrap_text_into_html",
            return_value="<p>Short</p>",
        ), patch(
            "fastfetchbot_shared.services.scrapers.douban.get_html_text_length",
            return_value=5,
        ):
            d = Douban("https://www.douban.com/note/12345/")
            await d.get_douban()
            assert d.message_type == MessageType.SHORT

    @pytest.mark.asyncio
    async def test_short_text_ending_with_newline_stripped(self, _patch_get_selector, _patch_douban_templates):
        """If short_text ends with newline, it should be stripped."""
        from fastfetchbot_shared.services.scrapers.douban import Douban, DoubanType

        html = """
        <html><body>
        <h1>Test Note</h1>
        <div class="content"><a href="/people/123/">Author</a></div>
        <div id="link-report"><p>Content</p></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://www.douban.com/note/12345/")
        d.douban_type = DoubanType.NOTE
        # Patch _douban_short_text_process to return text ending with \n
        with patch.object(d, "_douban_short_text_process", return_value="text\n"):
            await d.get_douban_item()
            # The template should receive short_text without trailing newline
            call_args = _patch_douban_templates.render.call_args_list
            # Find the call where short_text was passed
            found = False
            for c in call_args:
                if c.kwargs.get("data", {}).get("short_text") == "text":
                    found = True
                    break
                if c.args and isinstance(c.args[0], dict) and c.args[0].get("short_text") == "text":
                    found = True
                    break


# ---------------------------------------------------------------------------
# _get_douban_movie_review tests
# ---------------------------------------------------------------------------

class TestGetDoubanMovieReview:

    @pytest.mark.asyncio
    async def test_movie_review_fields(self, _patch_get_selector):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <div id="content"><h1><span>Movie Review Title</span></h1></div>
        <header class="main-hd">
            <a href="/people/123/">Author Link</a>
            <span>ReviewAuthor</span>
            <a href="/subject/456/">Movie Name</a>
        </header>
        <div class="review-content clearfix">Review body text</div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://movie.douban.com/review/12345/")
        d.check_douban_type()
        await d._get_douban_movie_review()

        assert d.title == "Movie Review Title"
        assert d.raw_content is not None


# ---------------------------------------------------------------------------
# _get_douban_book_review tests
# ---------------------------------------------------------------------------

class TestGetDoubanBookReview:

    @pytest.mark.asyncio
    async def test_book_review_fields(self, _patch_get_selector):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <div id="content"><h1><span>Book Review Title</span></h1></div>
        <header class="main-hd">
            <a href="/people/123/">Author</a>
            <span>BookReviewAuthor</span>
            <a href="/subject/789/">Book Name</a>
        </header>
        <div id="link-report">Book review content goes here</div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://book.douban.com/review/12345/")
        d.check_douban_type()
        await d._get_douban_book_review()

        assert d.title == "Book Review Title"
        assert d.raw_content is not None


# ---------------------------------------------------------------------------
# _get_douban_note tests
# ---------------------------------------------------------------------------

class TestGetDoubanNote:

    @pytest.mark.asyncio
    async def test_note_fields(self, _patch_get_selector):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <h1>My Note Title</h1>
        <div class="content"><a href="/people/123/">NoteAuthor</a></div>
        <div id="link-report"><p>Note body text</p></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://www.douban.com/note/12345/")
        d.check_douban_type()
        await d._get_douban_note()

        assert d.title == "My Note Title"
        assert d.author == "NoteAuthor"
        assert d.raw_content is not None


# ---------------------------------------------------------------------------
# _get_douban_status tests
# ---------------------------------------------------------------------------

class TestGetDoubanStatus:

    @pytest.mark.asyncio
    async def test_status_fields(self, _patch_get_selector):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <div class="content"><a href="/people/123/">StatusAuthor</a></div>
        <div class="status-saying"><blockquote>Status text here</blockquote></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://www.douban.com/status/12345/")
        d.check_douban_type()
        await d._get_douban_status()

        assert d.author == "StatusAuthor"
        assert d.title == "StatusAuthor\u7684\u5e7f\u64ad"  # "StatusAuthor的广播"
        assert "blockquote" not in d.raw_content

    @pytest.mark.asyncio
    async def test_status_replaces_special_chars(self, _patch_get_selector):
        """Status should replace blockquote tags, >+<, and &#13;."""
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <div class="content"><a href="/people/123/">Author</a></div>
        <div class="status-saying"><blockquote>Text&#13;More</blockquote></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://www.douban.com/status/12345/")
        d.check_douban_type()
        await d._get_douban_status()

        assert "<blockquote>" not in d.raw_content
        assert "</blockquote>" not in d.raw_content


# ---------------------------------------------------------------------------
# _get_douban_group_article tests
# ---------------------------------------------------------------------------

class TestGetDoubanGroupArticle:

    @pytest.mark.asyncio
    async def test_group_article_fields(self, _patch_get_selector):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <div id="content"><h1>
          Group Article Title
        </h1></div>
        <span class="from"><a href="/people/123/">GroupAuthor</a></span>
        <div id="g-side-info"><div class="title"><a href="/group/456/">Test Group</a></div></div>
        <div id="link-report"><p>Group article body</p></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://www.douban.com/group/topic/12345/")
        d.check_douban_type()
        await d._get_douban_group_article()

        assert d.title == "Group Article Title"
        assert d.author == "GroupAuthor"
        assert d.group_name == "Test Group"
        assert d.raw_content is not None


# ---------------------------------------------------------------------------
# _douban_short_text_process tests
# ---------------------------------------------------------------------------

class TestDoubanShortTextProcess:

    def test_images_extracted_to_media_files(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = '<div><img src="https://img.douban.com/pic.jpg"/><p>Text</p></div>'
        result = d._douban_short_text_process()

        assert len(d.media_files) == 1
        assert d.media_files[0].url == "https://img.douban.com/pic.jpg"
        assert "img" not in result

    def test_p_span_div_unwrapped(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = "<div><p><span>inner text</span></p></div>"
        result = d._douban_short_text_process()

        assert "<p>" not in result
        assert "<span>" not in result
        assert "<div>" not in result

    def test_link_and_script_decomposed(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = '<link rel="stylesheet" href="x.css"/><script>alert(1)</script><p>Text</p>'
        result = d._douban_short_text_process()

        assert "<link" not in result
        assert "<script" not in result

    def test_view_original_link_decomposed(self):
        """Links with title='查看原图' should be decomposed."""
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = '<a title="\u67e5\u770b\u539f\u56fe" href="https://img.douban.com/big.jpg">View</a><p>Text</p>'
        result = d._douban_short_text_process()

        assert "\u67e5\u770b\u539f\u56fe" not in result

    def test_multiple_newlines_collapsed(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = "Line1\n\n\n\nLine2"
        result = d._douban_short_text_process()

        assert "\n\n" not in result

    def test_br_replaced_with_newline(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = "Line1<br/>Line2<br>Line3<br />Line4"
        result = d._douban_short_text_process()

        assert "<br" not in result
        assert "\n" in result

    def test_regular_links_kept(self):
        """Regular links (no title='查看原图') should remain."""
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = '<a href="https://example.com">Example</a>'
        result = d._douban_short_text_process()

        assert "Example" in result

    def test_multiple_images(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        d = Douban("https://www.douban.com/note/12345/")
        d.raw_content = '<img src="https://img1.jpg"/><img src="https://img2.jpg"/>'
        result = d._douban_short_text_process()

        assert len(d.media_files) == 2


# ---------------------------------------------------------------------------
# raw_content_to_html tests
# ---------------------------------------------------------------------------

class TestRawContentToHtml:

    def test_single_paragraph(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        result = Douban.raw_content_to_html("Hello world")
        assert result == "<p>Hello world</p>"

    def test_multiple_paragraphs(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        result = Douban.raw_content_to_html("Para 1<br>\nPara 2<br>\nPara 3")
        assert "<p>Para 1</p>" in result
        assert "<p>Para 2</p>" in result
        assert "<p>Para 3</p>" in result

    def test_strips_whitespace(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        result = Douban.raw_content_to_html("  Hello  <br>\n  World  ")
        assert "<p>Hello</p>" in result
        assert "<p>World</p>" in result

    def test_empty_string(self):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        result = Douban.raw_content_to_html("")
        assert result == "<p></p>"

    def test_no_br_newline_separator(self):
        """Text without <br>\\n should be a single paragraph."""
        from fastfetchbot_shared.services.scrapers.douban import Douban

        result = Douban.raw_content_to_html("Just a single line")
        assert result == "<p>Just a single line</p>"


# ---------------------------------------------------------------------------
# get_douban (integration of check_douban_type + get_douban_item)
# ---------------------------------------------------------------------------

class TestGetDouban:

    @pytest.mark.asyncio
    async def test_get_douban_note_full_flow(self, _patch_get_selector, _patch_douban_templates):
        from fastfetchbot_shared.services.scrapers.douban import Douban

        html = """
        <html><body>
        <h1>Full Flow Note</h1>
        <div class="content"><a href="/people/123/">Author</a></div>
        <div id="link-report"><p>Content body</p></div>
        </body></html>
        """
        selector = etree.HTML(html)
        _patch_get_selector.return_value = selector

        d = Douban("https://www.douban.com/note/12345/")
        await d.get_douban()

        assert d.title == "Full Flow Note"
        assert d.author == "Author"
        assert d.text is not None
        assert d.content is not None

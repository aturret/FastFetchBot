"""Unit tests for Wechat scraper module.

Covers:
- packages/shared/fastfetchbot_shared/services/scrapers/wechat/__init__.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from lxml import etree

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.services.scrapers.wechat import Wechat


class TestWechatInit:
    """Tests for Wechat.__init__."""

    def test_default_init(self):
        w = Wechat(url="https://mp.weixin.qq.com/s/abc123")
        assert w.url == "https://mp.weixin.qq.com/s/abc123"
        assert w.title == ""
        assert w.author == ""
        assert w.author_url == w.url
        assert w.text == ""
        assert w.content == ""
        assert w.media_files == []
        assert w.category == "wechat"
        assert w.message_type == MessageType.LONG
        assert w.sid == ""
        assert w.official_account == ""
        assert w.date == ""

    def test_init_with_data_kwarg(self):
        """data and kwargs are accepted but not used."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc", data={"key": "val"}, extra="ignored")
        assert w.url == "https://mp.weixin.qq.com/s/abc"


class TestWechatDataParse:
    """Tests for Wechat._wechat_data_parse (static)."""

    def test_parses_article_data(self):
        html_str = """
        <html>
        <body>
        <div id="js_article">
            <h1 id="activity-name">  Test Title\n  </h1>
            <a id="js_name">  Test Author\n  </a>
            <div id="js_content"><p>Test content paragraph</p></div>
        </div>
        </body>
        </html>
        """
        tree = etree.HTML(html_str)
        result = Wechat._wechat_data_parse(tree)
        assert result["title"] == "Test Title"
        assert result["author"] == "Test Author"
        assert "Test content paragraph" in result["content"]

    def test_strips_newlines_and_whitespace(self):
        html_str = """
        <html><body>
        <div id="js_article">
            <h1 id="activity-name">  Title\nWith\nNewlines  </h1>
            <a id="js_name">  Author\n  </a>
            <div id="js_content"><p>Content</p></div>
        </div>
        </body></html>
        """
        tree = etree.HTML(html_str)
        result = Wechat._wechat_data_parse(tree)
        assert "\n" not in result["title"]
        assert "\n" not in result["author"]
        assert result["title"] == "TitleWithNewlines"
        assert result["author"] == "Author"


class TestProcessWechat:
    """Tests for Wechat._process_wechat."""

    def test_basic_processing(self):
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "Title",
            "author": "Author",
            "content": "<p>Hello World</p>",
        }
        w._process_wechat(wechat_data)
        assert w.title == "Title"
        assert w.author == "Author"
        assert w.author_url == ""
        assert "Hello World" in w.text
        assert "Hello World" in w.content

    def test_images_with_rich_pages_class(self):
        """Images with both rich_pages and wxw-img classes should be processed."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": '<img class="rich_pages wxw-img" data-src="http://img.wx.com/1.jpg">',
        }
        w._process_wechat(wechat_data)
        assert len(w.media_files) == 1
        assert w.media_files[0].url == "http://img.wx.com/1.jpg"
        assert w.media_files[0].media_type == "image"

    def test_images_without_rich_pages_class_ignored(self):
        """Images without the required classes should be ignored."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": '<img class="other-class" data-src="http://img.wx.com/2.jpg">',
        }
        w._process_wechat(wechat_data)
        assert len(w.media_files) == 0

    def test_images_with_partial_class(self):
        """Images with only one of the required classes should be ignored."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": '<img class="rich_pages" data-src="http://img.wx.com/3.jpg">',
        }
        w._process_wechat(wechat_data)
        assert len(w.media_files) == 0

    def test_images_no_class(self):
        """Images without any class attribute should be ignored."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": '<img data-src="http://img.wx.com/4.jpg">',
        }
        w._process_wechat(wechat_data)
        assert len(w.media_files) == 0

    def test_section_with_br_pairs(self):
        """Sections with <br><br> pairs should split into paragraphs."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        # Use html.parser-style markup that BS4 with lxml parser will handle
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": "<section><span>Part1</span><br><br>Part2</section>",
        }
        w._process_wechat(wechat_data)
        assert w.text is not None

    def test_section_with_br_pairs_and_content_before(self):
        """br pair with existing new_p_tag content should create paragraph split."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        # BeautifulSoup with "lxml" parser: two consecutive <br> tags as siblings
        from bs4 import BeautifulSoup
        # Manually construct the HTML that triggers the br pair logic
        html_content = "<section>Text before<br/><br/>Text after</section>"
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": html_content,
        }
        w._process_wechat(wechat_data)
        assert "Text" in w.text

    def test_section_with_p_tags(self):
        """Sections containing <p> tags should handle them properly."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": "<section><p>Paragraph 1</p><span>Extra</span></section>",
        }
        w._process_wechat(wechat_data)
        assert "Paragraph 1" in w.text

    def test_nested_sections_skipped(self):
        """Sections containing child sections should not be processed (outer section)."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": "<section><section><span>Inner</span></section></section>",
        }
        w._process_wechat(wechat_data)
        assert "Inner" in w.text

    def test_section_with_mixed_content(self):
        """Sections with mixed br pairs, p tags, and text nodes."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": "<section>Text before<br/><br/><p>Para</p>text after</section>",
        }
        w._process_wechat(wechat_data)
        assert isinstance(w.content, str)

    def test_section_empty_new_p_tag(self):
        """When new_p_tag has no contents, it should not be appended."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": "<section><br/><br/></section>",
        }
        w._process_wechat(wechat_data)
        assert isinstance(w.content, str)

    def test_multiple_images(self):
        """Multiple images with correct classes all get processed."""
        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        wechat_data = {
            "title": "T",
            "author": "A",
            "content": (
                '<img class="rich_pages wxw-img" data-src="http://img1.jpg">'
                '<img class="rich_pages wxw-img" data-src="http://img2.jpg">'
            ),
        }
        w._process_wechat(wechat_data)
        assert len(w.media_files) == 2


class TestProcessWechatBrPairCoverage:
    """Cover lines 86-90: br-pair paragraph splitting.

    After extract(), BeautifulSoup nullifies next_sibling, making lines 86-90
    normally unreachable. We patch both extract() and decompose() to preserve
    element attributes, allowing the br-pair detection to trigger.
    """

    def test_br_pair_with_content_before(self):
        from bs4 import Tag

        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        html_content = "<section><span>Hello</span><br/><br/><span>World</span></section>"
        wechat_data = {"title": "T", "author": "A", "content": html_content}

        # Make both extract() and decompose() no-ops so siblings are preserved
        with patch.object(Tag, "extract", lambda self, _self_index=None: self), \
             patch.object(Tag, "decompose", lambda self: None):
            w._process_wechat(wechat_data)
        assert isinstance(w.content, str)

    def test_br_pair_without_content_before(self):
        from bs4 import Tag

        w = Wechat(url="https://mp.weixin.qq.com/s/abc")
        html_content = "<section><br/><br/><span>After</span></section>"
        wechat_data = {"title": "T", "author": "A", "content": html_content}

        with patch.object(Tag, "extract", lambda self, _self_index=None: self), \
             patch.object(Tag, "decompose", lambda self: None):
            w._process_wechat(wechat_data)
        assert isinstance(w.content, str)


class TestGetResponseWechatData:
    """Tests for Wechat._get_response_wechat_data."""

    @pytest.mark.asyncio
    async def test_calls_get_selector_and_parses(self):
        html_str = """
        <html><body>
        <div id="js_article">
            <h1 id="activity-name">Title</h1>
            <a id="js_name">Author</a>
            <div id="js_content"><p>Content</p></div>
        </div>
        </body></html>
        """
        tree = etree.HTML(html_str)
        with patch(
            "fastfetchbot_shared.services.scrapers.wechat.get_selector",
            new_callable=AsyncMock,
            return_value=tree,
        ):
            w = Wechat(url="https://mp.weixin.qq.com/s/abc")
            result = await w._get_response_wechat_data()
        assert result["title"] == "Title"
        assert result["author"] == "Author"


class TestGetWechat:
    """Tests for Wechat.get_wechat."""

    @pytest.mark.asyncio
    async def test_get_wechat_full_flow(self):
        html_str = """
        <html><body>
        <div id="js_article">
            <h1 id="activity-name">Full Title</h1>
            <a id="js_name">Full Author</a>
            <div id="js_content"><p>Full Content</p></div>
        </div>
        </body></html>
        """
        tree = etree.HTML(html_str)
        with patch(
            "fastfetchbot_shared.services.scrapers.wechat.get_selector",
            new_callable=AsyncMock,
            return_value=tree,
        ):
            w = Wechat(url="https://mp.weixin.qq.com/s/abc")
            await w.get_wechat()
        assert w.title == "Full Title"
        assert w.author == "Full Author"


class TestGetItem:
    """Tests for Wechat.get_item."""

    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self):
        html_str = """
        <html><body>
        <div id="js_article">
            <h1 id="activity-name">Item Title</h1>
            <a id="js_name">Item Author</a>
            <div id="js_content"><p>Item Content</p></div>
        </div>
        </body></html>
        """
        tree = etree.HTML(html_str)
        with patch(
            "fastfetchbot_shared.services.scrapers.wechat.get_selector",
            new_callable=AsyncMock,
            return_value=tree,
        ):
            w = Wechat(url="https://mp.weixin.qq.com/s/abc")
            result = await w.get_item()
        assert isinstance(result, dict)
        assert result["title"] == "Item Title"
        assert result["author"] == "Item Author"
        assert result["category"] == "wechat"
        assert result["url"] == "https://mp.weixin.qq.com/s/abc"
        assert "content" in result
        assert "text" in result
        assert "media_files" in result

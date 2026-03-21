"""Tests for Zhihu content processing functions."""

import pytest

from fastfetchbot_shared.services.scrapers.zhihu.content_processing import (
    extract_references,
    fix_images_and_links,
    unmask_zhihu_links,
)


class TestFixImagesAndLinks:
    """Tests for fix_images_and_links function."""

    def test_replaces_data_actualsrc_with_src(self):
        html = '<img data-actualsrc="https://pic.zhimg.com/real.jpg" src="https://pic.zhimg.com/thumb.jpg">'
        result = fix_images_and_links(html)
        assert 'src="https://pic.zhimg.com/real.jpg"' in result
        assert "data-actualsrc" not in result

    def test_img_without_data_actualsrc_unchanged(self):
        html = '<img src="https://example.com/image.jpg">'
        result = fix_images_and_links(html)
        assert 'src="https://example.com/image.jpg"' in result

    def test_removes_u_tags_preserving_content(self):
        html = "<p>Some <u>underlined</u> text</p>"
        result = fix_images_and_links(html)
        assert "<u>" not in result
        assert "underlined" in result
        assert "<p>" in result

    def test_multiple_img_tags(self):
        html = (
            '<img data-actualsrc="https://a.com/1.jpg" src="thumb1.jpg">'
            '<img data-actualsrc="https://a.com/2.jpg" src="thumb2.jpg">'
        )
        result = fix_images_and_links(html)
        assert 'src="https://a.com/1.jpg"' in result
        assert 'src="https://a.com/2.jpg"' in result
        assert "data-actualsrc" not in result

    def test_multiple_u_tags(self):
        html = "<p><u>first</u> and <u>second</u></p>"
        result = fix_images_and_links(html)
        assert "<u>" not in result
        assert "first" in result
        assert "second" in result

    def test_empty_string(self):
        result = fix_images_and_links("")
        assert result == ""

    def test_no_matching_elements(self):
        html = "<p>Just plain text</p>"
        result = fix_images_and_links(html)
        assert "Just plain text" in result

    def test_img_with_only_data_actualsrc_no_existing_src(self):
        html = '<img data-actualsrc="https://pic.zhimg.com/real.jpg">'
        result = fix_images_and_links(html)
        assert 'src="https://pic.zhimg.com/real.jpg"' in result
        assert "data-actualsrc" not in result


class TestExtractReferences:
    """Tests for extract_references function."""

    def test_extracts_single_reference(self):
        html = '<p>Some text<sup data-text="Ref text" data-url="https://example.com" data-numero="1"></sup></p>'
        result = extract_references(html)
        assert "<h2>参考</h2>" in result
        assert "Ref text" in result
        assert "https://example.com" in result
        assert "<ol>" in result

    def test_extracts_multiple_references_sorted(self):
        html = (
            '<sup data-text="Second" data-url="https://b.com" data-numero="2"></sup>'
            '<sup data-text="First" data-url="https://a.com" data-numero="1"></sup>'
        )
        result = extract_references(html)
        first_pos = result.index("First")
        second_pos = result.index("Second")
        assert first_pos < second_pos

    def test_reference_without_url(self):
        html = '<sup data-text="No URL ref" data-numero="1"></sup>'
        result = extract_references(html)
        assert "No URL ref" in result
        assert "<a href=" not in result

    def test_reference_with_empty_url(self):
        html = '<sup data-text="Empty URL" data-url="" data-numero="1"></sup>'
        result = extract_references(html)
        assert "Empty URL" in result
        assert "<a href=" not in result

    def test_no_references_returns_empty(self):
        html = "<p>No references here</p>"
        result = extract_references(html)
        assert result == ""

    def test_sup_without_data_text_ignored(self):
        html = '<sup data-url="https://example.com" data-numero="1"></sup>'
        result = extract_references(html)
        assert result == ""

    def test_sup_without_data_numero_ignored(self):
        html = '<sup data-text="Some text" data-url="https://example.com"></sup>'
        result = extract_references(html)
        assert result == ""

    def test_empty_string(self):
        result = extract_references("")
        assert result == ""

    def test_reference_output_format(self):
        html = '<sup data-text="My ref" data-url="https://example.com/page" data-numero="1"></sup>'
        result = extract_references(html)
        assert result.startswith("<hr>")
        assert "<section>" in result
        assert "<li>" in result
        assert "</ol></section>" in result


class TestUnmaskZhihuLinks:
    """Tests for unmask_zhihu_links function."""

    def test_unmasks_zhihu_redirect_link(self):
        html = '<a href="https://link.zhihu.com/?target=https%3A%2F%2Fexample.com%2Fpage">link</a>'
        result = unmask_zhihu_links(html)
        assert 'href="https://example.com/page"' in result

    def test_non_zhihu_link_unchanged(self):
        html = '<a href="https://example.com/page">link</a>'
        result = unmask_zhihu_links(html)
        assert 'href="https://example.com/page"' in result

    def test_multiple_links_mixed(self):
        html = (
            '<a href="https://link.zhihu.com/?target=https%3A%2F%2Fa.com">A</a>'
            '<a href="https://b.com">B</a>'
            '<a href="https://link.zhihu.com/?target=https%3A%2F%2Fc.com">C</a>'
        )
        result = unmask_zhihu_links(html)
        assert 'href="https://a.com"' in result
        assert 'href="https://b.com"' in result
        assert 'href="https://c.com"' in result

    def test_zhihu_link_without_target_param(self):
        html = '<a href="https://link.zhihu.com/?other=value">link</a>'
        result = unmask_zhihu_links(html)
        # No target param, so href should remain unchanged
        assert 'href="https://link.zhihu.com/?other=value"' in result

    def test_empty_string(self):
        result = unmask_zhihu_links("")
        assert result == ""

    def test_no_links(self):
        html = "<p>No links here</p>"
        result = unmask_zhihu_links(html)
        assert "No links here" in result

    def test_encoded_target_decoded(self):
        html = '<a href="https://link.zhihu.com/?target=https%3A%2F%2Fexample.com%2Fpath%3Fq%3Dhello%26p%3D1">link</a>'
        result = unmask_zhihu_links(html)
        assert "https://example.com/path?q=hello&" in result

    def test_a_tag_without_href_skipped(self):
        html = "<a>no href</a>"
        result = unmask_zhihu_links(html)
        assert "no href" in result

    def test_malformed_zhihu_link_handled_gracefully(self):
        """A zhihu link that causes a parsing error is left unchanged."""
        from unittest.mock import patch

        html = '<a href="https://link.zhihu.com/?target=https%3A%2F%2Fexample.com">link</a>'
        with patch(
            "fastfetchbot_shared.services.scrapers.zhihu.content_processing.parse_qs",
            side_effect=Exception("parse error"),
        ):
            result = unmask_zhihu_links(html)
        # The link should remain unchanged since the exception was caught
        assert "link.zhihu.com" in result

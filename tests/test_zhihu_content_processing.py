import sys
import os

# Import content_processing directly to avoid pulling in the full zhihu scraper
# which has heavy dependencies (fastfetchbot_shared, httpx, etc.)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api", "src", "services", "scrapers", "zhihu"))
from content_processing import (
    fix_images_and_links,
    extract_references,
    unmask_zhihu_links,
)


def test_fix_images_replaces_data_actualsrc():
    html = '<img src="placeholder.jpg" data-actualsrc="https://real.jpg">'
    result = fix_images_and_links(html)
    assert 'src="https://real.jpg"' in result
    assert "data-actualsrc" not in result


def test_fix_images_preserves_normal_src():
    html = '<img src="https://normal.jpg">'
    result = fix_images_and_links(html)
    assert 'src="https://normal.jpg"' in result


def test_fix_images_removes_u_tags():
    html = "<p>Hello <u>world</u></p>"
    result = fix_images_and_links(html)
    assert "<u>" not in result
    assert "world" in result


def test_extract_references_with_refs():
    html = '<p>Text<sup data-text="Ref 1" data-url="https://example.com" data-numero="1">[1]</sup></p>'
    result = extract_references(html)
    assert "参考" in result
    assert "Ref 1" in result
    assert "https://example.com" in result


def test_extract_references_empty():
    html = "<p>No references here</p>"
    result = extract_references(html)
    assert result == ""


def test_unmask_zhihu_links():
    html = '<a href="https://link.zhihu.com/?target=https%3A%2F%2Fexample.com">link</a>'
    result = unmask_zhihu_links(html)
    assert "https://example.com" in result
    assert "link.zhihu.com" not in result


def test_unmask_preserves_normal_links():
    html = '<a href="https://example.com">link</a>'
    result = unmask_zhihu_links(html)
    assert 'href="https://example.com"' in result

"""Tests for GeneralItem dataclass."""

import pytest

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.services.scrapers.general import GeneralItem


class TestGeneralItemFromDict:
    """Tests for GeneralItem.from_dict class method."""

    def test_from_dict_with_all_fields(self):
        data = {
            "url": "https://example.com/article",
            "title": "Test Article",
            "author": "Author Name",
            "author_url": "https://example.com/author",
            "telegraph_url": "https://telegra.ph/test",
            "text": "Summary text",
            "content": "<p>Full content</p>",
            "media_files": [
                {"media_type": "image", "url": "https://example.com/img.jpg", "caption": "Photo"},
            ],
            "category": "general",
            "message_type": "short",
            "id": "abc123",
            "raw_content": "<html>raw</html>",
            "scraper_type": "firecrawl",
        }
        item = GeneralItem.from_dict(data)
        assert item.url == "https://example.com/article"
        assert item.title == "Test Article"
        assert item.author == "Author Name"
        assert item.author_url == "https://example.com/author"
        assert item.telegraph_url == "https://telegra.ph/test"
        assert item.text == "Summary text"
        assert item.content == "<p>Full content</p>"
        assert len(item.media_files) == 1
        assert item.media_files[0].media_type == "image"
        assert item.category == "general"
        assert item.message_type == MessageType.SHORT
        assert item.id == "abc123"
        assert item.raw_content == "<html>raw</html>"
        assert item.scraper_type == "firecrawl"

    def test_from_dict_with_defaults_for_general_fields(self):
        data = {
            "url": "https://example.com",
            "title": "",
            "author": "",
            "author_url": "",
            "telegraph_url": "",
            "text": "",
            "content": "",
            "media_files": [],
            "category": "",
            "message_type": "short",
        }
        item = GeneralItem.from_dict(data)
        assert item.id == ""
        assert item.raw_content == ""
        assert item.scraper_type == ""

    def test_from_dict_preserves_metadata_fields(self):
        data = {
            "url": "https://test.com",
            "title": "Title",
            "author": "Author",
            "author_url": "",
            "telegraph_url": "",
            "text": "text",
            "content": "content",
            "media_files": [],
            "category": "news",
            "message_type": "long",
            "id": "x",
            "raw_content": "raw",
            "scraper_type": "zyte",
        }
        item = GeneralItem.from_dict(data)
        assert item.url == "https://test.com"
        assert item.message_type == MessageType.LONG


class TestGeneralItemToDict:
    """Tests for GeneralItem.to_dict method."""

    def test_to_dict_includes_general_fields(self):
        item = GeneralItem(
            url="https://example.com",
            title="Title",
            author="Author",
            author_url="",
            telegraph_url="",
            text="text",
            content="content",
            media_files=[],
            category="general",
            message_type=MessageType.SHORT,
            id="item-1",
            raw_content="<html>raw</html>",
            scraper_type="firecrawl",
        )
        d = item.to_dict()
        assert d["id"] == "item-1"
        assert d["raw_content"] == "<html>raw</html>"
        assert d["scraper_type"] == "firecrawl"

    def test_to_dict_includes_base_fields(self):
        item = GeneralItem(
            url="https://example.com",
            title="My Title",
            author="Jane",
            author_url="https://example.com/jane",
            telegraph_url="",
            text="summary",
            content="<p>body</p>",
            media_files=[],
            category="blog",
            message_type=MessageType.LONG,
            id="",
            raw_content="",
            scraper_type="",
        )
        d = item.to_dict()
        assert d["url"] == "https://example.com"
        assert d["title"] == "My Title"
        assert d["author"] == "Jane"
        assert d["author_url"] == "https://example.com/jane"
        assert d["text"] == "summary"
        assert d["content"] == "<p>body</p>"
        assert d["category"] == "blog"
        assert d["message_type"] == "long"

    def test_to_dict_with_media_files(self):
        media = MediaFile(media_type="image", url="https://example.com/img.jpg", caption="cap")
        item = GeneralItem(
            url="https://example.com",
            title="",
            author="",
            author_url="",
            telegraph_url="",
            text="",
            content="",
            media_files=[media],
            category="",
            message_type=MessageType.SHORT,
            id="",
            raw_content="",
            scraper_type="",
        )
        d = item.to_dict()
        assert len(d["media_files"]) == 1
        assert d["media_files"][0]["media_type"] == "image"
        assert d["media_files"][0]["url"] == "https://example.com/img.jpg"


class TestGeneralItemDefaults:
    """Tests for GeneralItem default field values."""

    def test_general_specific_defaults(self):
        item = GeneralItem(
            url="https://example.com",
            title="",
            author="",
            author_url="",
            telegraph_url="",
            text="",
            content="",
            media_files=[],
            category="",
            message_type=MessageType.SHORT,
        )
        assert item.id == ""
        assert item.raw_content == ""
        assert item.scraper_type == ""

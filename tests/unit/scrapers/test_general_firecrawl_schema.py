"""Tests for Firecrawl extraction Pydantic schema."""

import pytest

from fastfetchbot_shared.services.scrapers.general.firecrawl_schema import (
    FIRECRAWL_EXTRACTION_PROMPT,
    ExtractedArticle,
    ExtractedMediaFile,
)


class TestExtractedMediaFile:
    """Tests for ExtractedMediaFile Pydantic model."""

    def test_required_fields(self):
        media = ExtractedMediaFile(media_type="image", url="https://example.com/img.jpg")
        assert media.media_type == "image"
        assert media.url == "https://example.com/img.jpg"

    def test_optional_fields_default_to_none(self):
        media = ExtractedMediaFile(media_type="video", url="https://example.com/vid.mp4")
        assert media.original_url is None
        assert media.caption is None

    def test_all_fields_set(self):
        media = ExtractedMediaFile(
            media_type="audio",
            url="https://example.com/audio.mp3",
            original_url="https://source.com/audio.mp3",
            caption="A podcast episode",
        )
        assert media.media_type == "audio"
        assert media.url == "https://example.com/audio.mp3"
        assert media.original_url == "https://source.com/audio.mp3"
        assert media.caption == "A podcast episode"

    def test_serialization(self):
        media = ExtractedMediaFile(
            media_type="image",
            url="https://example.com/img.jpg",
            caption="A photo",
        )
        data = media.model_dump()
        assert data["media_type"] == "image"
        assert data["url"] == "https://example.com/img.jpg"
        assert data["caption"] == "A photo"
        assert data["original_url"] is None


class TestExtractedArticle:
    """Tests for ExtractedArticle Pydantic model."""

    def test_defaults(self):
        article = ExtractedArticle()
        assert article.title == ""
        assert article.author == ""
        assert article.author_url is None
        assert article.text == ""
        assert article.content == ""
        assert article.media_files == []

    def test_all_fields_set(self):
        media = ExtractedMediaFile(media_type="image", url="https://example.com/img.jpg")
        article = ExtractedArticle(
            title="Test Article",
            author="John Doe",
            author_url="https://example.com/john",
            text="A brief summary of the article.",
            content="<p>Full article content here.</p>",
            media_files=[media],
        )
        assert article.title == "Test Article"
        assert article.author == "John Doe"
        assert article.author_url == "https://example.com/john"
        assert article.text == "A brief summary of the article."
        assert article.content == "<p>Full article content here.</p>"
        assert len(article.media_files) == 1
        assert article.media_files[0].media_type == "image"

    def test_media_files_default_is_empty_list(self):
        article = ExtractedArticle(title="No media")
        assert article.media_files == []
        # Ensure default_factory creates independent lists
        article2 = ExtractedArticle(title="Also no media")
        assert article.media_files is not article2.media_files

    def test_serialization(self):
        article = ExtractedArticle(
            title="Serialization Test",
            author="Author",
            content="<p>Content</p>",
            media_files=[
                ExtractedMediaFile(media_type="image", url="https://example.com/1.jpg"),
            ],
        )
        data = article.model_dump()
        assert data["title"] == "Serialization Test"
        assert data["author"] == "Author"
        assert len(data["media_files"]) == 1
        assert data["media_files"][0]["url"] == "https://example.com/1.jpg"

    def test_multiple_media_files(self):
        files = [
            ExtractedMediaFile(media_type="image", url="https://example.com/1.jpg"),
            ExtractedMediaFile(media_type="video", url="https://example.com/2.mp4"),
            ExtractedMediaFile(media_type="audio", url="https://example.com/3.mp3"),
        ]
        article = ExtractedArticle(media_files=files)
        assert len(article.media_files) == 3


class TestFirecrawlExtractionPrompt:
    """Tests for the FIRECRAWL_EXTRACTION_PROMPT constant."""

    def test_prompt_is_non_empty_string(self):
        assert isinstance(FIRECRAWL_EXTRACTION_PROMPT, str)
        assert len(FIRECRAWL_EXTRACTION_PROMPT) > 0

    def test_prompt_mentions_extraction(self):
        assert "Extract" in FIRECRAWL_EXTRACTION_PROMPT

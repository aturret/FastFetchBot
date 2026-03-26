"""Tests for packages/shared/fastfetchbot_shared/services/telegraph/__init__.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.services.telegraph import Telegraph


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestTelegraphInit:
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    def test_init_sets_all_fields(self, mock_poster_cls):
        mock_poster_cls.return_value = MagicMock()
        t = Telegraph(
            title="My Title",
            url="https://example.com/post",
            author="Author Name",
            author_url="https://example.com/author",
            category="tech",
            content="<p>Hello</p>",
        )
        assert t.title == "My Title"
        assert t.url == "https://example.com/post"
        assert t.author == "Author Name"
        assert t.author_url == "https://example.com/author"
        assert t.category == "tech"
        assert t.content == "<p>Hello</p>"
        mock_poster_cls.assert_called_once_with(use_api=True)
        assert t.telegraph is mock_poster_cls.return_value


# ---------------------------------------------------------------------------
# from_dict
# ---------------------------------------------------------------------------


class TestFromDict:
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    def test_from_dict(self, mock_poster_cls):
        mock_poster_cls.return_value = MagicMock()
        obj = {
            "title": "Title",
            "url": "https://example.com",
            "author": "Auth",
            "author_url": "https://example.com/auth",
            "category": "cat",
            "content": "<p>content</p>",
        }
        t = Telegraph.from_dict(obj)
        assert isinstance(t, Telegraph)
        assert t.title == "Title"
        assert t.url == "https://example.com"
        assert t.author == "Auth"
        assert t.author_url == "https://example.com/auth"
        assert t.category == "cat"
        assert t.content == "<p>content</p>"

    def test_from_dict_non_dict_raises(self):
        with pytest.raises(AssertionError):
            Telegraph.from_dict("not a dict")


# ---------------------------------------------------------------------------
# get_telegraph
# ---------------------------------------------------------------------------


class TestGetTelegraph:
    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.TELEGRAPH_TOKEN_LIST", "tok1,tok2")
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    @patch("fastfetchbot_shared.services.telegraph.DocumentPreprocessor")
    async def test_upload_images_true_with_token_list(
        self, mock_doc_pre_cls, mock_poster_cls
    ):
        # Setup mock poster
        mock_poster = AsyncMock()
        mock_poster_cls.return_value = mock_poster
        mock_poster.post.return_value = {"url": "https://telegra.ph/test-page"}

        # Setup mock DocumentPreprocessor
        mock_doc_pre = MagicMock()
        mock_doc_pre.upload_all_images = AsyncMock()
        mock_doc_pre.get_processed_html.return_value = "<p>processed</p>"
        mock_doc_pre_cls.return_value = mock_doc_pre

        t = Telegraph("T", "https://ex.com", "Auth", "https://ex.com/a", "cat", "<p>c</p>")

        result = await t.get_telegraph(upload_images=True)

        assert result == "https://telegra.ph/test-page"
        mock_doc_pre_cls.assert_called_once_with("<p>c</p>", url="https://ex.com")
        mock_doc_pre.upload_all_images.assert_awaited_once()
        mock_poster.set_token.assert_awaited_once()
        mock_poster.post.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.TELEGRAPH_TOKEN_LIST", "tok1")
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    async def test_upload_images_false(self, mock_poster_cls):
        mock_poster = AsyncMock()
        mock_poster_cls.return_value = mock_poster
        mock_poster.post.return_value = {"url": "https://telegra.ph/page"}

        t = Telegraph("T", "https://ex.com", "Auth", "https://ex.com/a", "cat", "<p>c</p>")
        result = await t.get_telegraph(upload_images=False)

        assert result == "https://telegra.ph/page"
        # DocumentPreprocessor should NOT have been called
        mock_poster.post.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.TELEGRAPH_TOKEN_LIST", "")
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    async def test_no_token_list_creates_token(self, mock_poster_cls):
        mock_poster = AsyncMock()
        mock_poster_cls.return_value = mock_poster
        mock_poster.post.return_value = {"url": "https://telegra.ph/page2"}

        t = Telegraph("T", "https://ex.com", "LongAuthorName12345", "https://ex.com/a", "cat", "<p>c</p>")
        result = await t.get_telegraph(upload_images=False)

        assert result == "https://telegra.ph/page2"
        mock_poster.create_api_token.assert_awaited_once_with(
            short_name="LongAuthorName", author_name="LongAuthorName12345"
        )
        mock_poster.set_token.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.TELEGRAPH_TOKEN_LIST", "")
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    async def test_empty_token_list_creates_token(self, mock_poster_cls):
        """Empty string parses to None (falsy), so it should create a token."""
        mock_poster = AsyncMock()
        mock_poster_cls.return_value = mock_poster
        mock_poster.post.return_value = {"url": "https://telegra.ph/page3"}

        t = Telegraph("T", "https://ex.com", "Auth", "https://ex.com/a", "cat", "<p>c</p>")
        result = await t.get_telegraph(upload_images=False)

        assert result == "https://telegra.ph/page3"
        mock_poster.create_api_token.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.TELEGRAPH_TOKEN_LIST", "tok")
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    async def test_exception_returns_empty_string(self, mock_poster_cls):
        mock_poster = AsyncMock()
        mock_poster_cls.return_value = mock_poster
        mock_poster.post.side_effect = RuntimeError("upload failed")

        t = Telegraph("T", "https://ex.com", "Auth", "https://ex.com/a", "cat", "<p>c</p>")
        result = await t.get_telegraph(upload_images=False)

        assert result == ""

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.TELEGRAPH_TOKEN_LIST", "tok")
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    @patch("fastfetchbot_shared.services.telegraph.DocumentPreprocessor")
    async def test_exception_during_image_upload_returns_empty(
        self, mock_doc_pre_cls, mock_poster_cls
    ):
        mock_poster = AsyncMock()
        mock_poster_cls.return_value = mock_poster

        mock_doc_pre = MagicMock()
        mock_doc_pre.upload_all_images = AsyncMock(side_effect=RuntimeError("img fail"))
        mock_doc_pre_cls.return_value = mock_doc_pre

        t = Telegraph("T", "https://ex.com", "Auth", "https://ex.com/a", "cat", "<p>c</p>")
        result = await t.get_telegraph(upload_images=True)

        assert result == ""

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.config.settings.TELEGRAPH_TOKEN_LIST", "tok")
    @patch("fastfetchbot_shared.services.telegraph.AsyncTelegraphPoster")
    @patch("fastfetchbot_shared.services.telegraph.DocumentPreprocessor")
    async def test_content_updated_after_image_processing(
        self, mock_doc_pre_cls, mock_poster_cls
    ):
        """Verify self.content is updated with processed HTML before posting."""
        mock_poster = AsyncMock()
        mock_poster_cls.return_value = mock_poster
        mock_poster.post.return_value = {"url": "https://telegra.ph/ok"}

        mock_doc_pre = MagicMock()
        mock_doc_pre.upload_all_images = AsyncMock()
        mock_doc_pre.get_processed_html.return_value = "<p>images-uploaded</p>"
        mock_doc_pre_cls.return_value = mock_doc_pre

        t = Telegraph("T", "https://ex.com", "Auth", "https://ex.com/a", "cat", "<p>original</p>")
        await t.get_telegraph(upload_images=True)

        # The content passed to post() should be the processed one
        post_call = mock_poster.post.call_args
        assert post_call.kwargs["text"] == "<p>images-uploaded</p>"
        assert t.content == "<p>images-uploaded</p>"

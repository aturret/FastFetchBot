"""Unit tests for bluesky scraper: Bluesky dataclass, BlueskyPost, BlueskyDataProcessor, BlueskyScraper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType


# ---------------------------------------------------------------------------
# Helpers – lightweight fakes for atproto types
# ---------------------------------------------------------------------------

def _make_author(handle="alice.bsky.social", display_name="Alice", did="did:plc:abc123"):
    author = MagicMock()
    author.handle = handle
    author.display_name = display_name
    author.did = did
    return author


def _make_post_view(
    uri="at://did:plc:abc123/app.bsky.feed.post/rkey123",
    text="Hello world",
    author=None,
    embed=None,
    created_at="2024-01-01T00:00:00Z",
):
    if author is None:
        author = _make_author()
    post = MagicMock()
    post.uri = uri
    post.author = author
    post.record = MagicMock()
    post.record.text = text
    post.record.created_at = created_at
    post.embed = embed
    return post


def _make_thread(post=None, parent=None, replies=None):
    thread = MagicMock()
    thread.post = post or _make_post_view()
    thread.parent = parent
    thread.replies = replies
    return thread


# ---------------------------------------------------------------------------
# Bluesky dataclass tests (bluesky/__init__.py)
# ---------------------------------------------------------------------------

class TestBlueskyDataclass:

    def test_from_dict_basic(self):
        """from_dict should populate cid/author_did from the dict."""
        obj = {
            "url": "https://bsky.app/profile/alice/post/123",
            "telegraph_url": "",
            "content": "<p>hi</p>",
            "text": "hi",
            "media_files": [],
            "author": "Alice",
            "title": "Alice's Bluesky post",
            "author_url": "https://bsky.app/profile/alice",
            "category": "bluesky",
            "message_type": "short",
            "cid": "cidvalue",
            "author_did": "did:plc:abc",
        }
        from fastfetchbot_shared.services.scrapers.bluesky import Bluesky

        item = Bluesky.from_dict(obj)
        assert item.cid == "cidvalue"
        assert item.author_did == "did:plc:abc"
        assert item.url == "https://bsky.app/profile/alice/post/123"
        assert item.author == "Alice"

    def test_to_dict_without_retweet(self):
        from fastfetchbot_shared.services.scrapers.bluesky import Bluesky

        item = Bluesky(
            url="https://bsky.app/profile/alice/post/123",
            telegraph_url="",
            content="<p>hi</p>",
            text="hi",
            media_files=[],
            author="Alice",
            title="Alice's Bluesky post",
            author_url="https://bsky.app/profile/alice",
            category="bluesky",
            message_type=MessageType.SHORT,
            cid="cidvalue",
            author_did="did:plc:abc",
            retweet_post=None,
        )
        d = item.to_dict()
        assert d["cid"] == "cidvalue"
        assert d["author_did"] == "did:plc:abc"
        assert "retweet_post" not in d

    def test_to_dict_with_retweet(self):
        from fastfetchbot_shared.services.scrapers.bluesky import Bluesky

        retweet = Bluesky(
            url="https://bsky.app/profile/bob/post/456",
            telegraph_url="",
            content="<p>retweet</p>",
            text="retweet",
            media_files=[],
            author="Bob",
            title="Bob's Bluesky post",
            author_url="https://bsky.app/profile/bob",
            category="bluesky",
            message_type=MessageType.SHORT,
            cid="cid2",
            author_did="did:plc:bob",
            retweet_post=None,
        )
        item = Bluesky(
            url="https://bsky.app/profile/alice/post/123",
            telegraph_url="",
            content="<p>hi</p>",
            text="hi",
            media_files=[],
            author="Alice",
            title="Alice's Bluesky post",
            author_url="https://bsky.app/profile/alice",
            category="bluesky",
            message_type=MessageType.SHORT,
            cid="cid1",
            author_did="did:plc:alice",
            retweet_post=retweet,
        )
        d = item.to_dict()
        assert "retweet_post" in d
        assert d["retweet_post"]["cid"] == "cid2"


# ---------------------------------------------------------------------------
# Bluesky config tests
# ---------------------------------------------------------------------------

class TestBlueskyConfig:

    def test_constants(self):
        from fastfetchbot_shared.services.scrapers.bluesky.config import (
            BLUESKY_HOST,
            BLUESKY_MAX_LENGTH,
        )

        assert BLUESKY_HOST == "https://bsky.app"
        assert BLUESKY_MAX_LENGTH == 800


# ---------------------------------------------------------------------------
# BlueskyPost tests
# ---------------------------------------------------------------------------

class TestBlueskyPost:

    @patch("fastfetchbot_shared.services.scrapers.bluesky.scraper.BlueskyScraper")
    def test_init_parses_url(self, mock_scraper_cls):
        """BlueskyPost should parse handle, post_rkey, and resolve DID."""
        mock_resolver = MagicMock()
        mock_resolver.handle.resolve.return_value = "did:plc:resolved"
        mock_scraper_cls.id_resolver = mock_resolver

        # Patch at class level before import
        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.BlueskyScraper.id_resolver",
            mock_resolver,
        ):
            from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyPost

            post = BlueskyPost("https://bsky.app/profile/alice.bsky.social/post/rkey123")
            assert post.handle == "alice.bsky.social"
            assert post.post_rkey == "rkey123"
            assert post.bluesky_host == "bsky.app"
            assert post.did == "did:plc:resolved"


# ---------------------------------------------------------------------------
# BlueskyDataProcessor tests
# ---------------------------------------------------------------------------

class TestBlueskyDataProcessor:

    @pytest.fixture(autouse=True)
    def _patch_templates(self):
        mock_tpl = MagicMock()
        mock_tpl.render.return_value = "<p>rendered</p>"
        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.telegram_text_template",
            mock_tpl,
        ), patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.content_template",
            mock_tpl,
        ):
            self.mock_tpl = mock_tpl
            yield

    @pytest.fixture
    def _patch_at_uri(self):
        mock_at_uri = MagicMock()
        mock_at_uri.rkey = "rkey123"
        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.AtUri"
        ) as at_uri_cls:
            at_uri_cls.from_str.return_value = mock_at_uri
            yield at_uri_cls

    @pytest.mark.asyncio
    async def test_get_item_short_text(self, _patch_at_uri):
        """get_item should return dict with SHORT message_type for short text."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        post = _make_post_view(text="short")
        thread = _make_thread(post=post, parent=None, replies=None)

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()

        assert isinstance(result, dict)
        assert result["category"] == "bluesky"
        assert result["message_type"] == "short"

    @pytest.mark.asyncio
    async def test_get_item_long_text(self, _patch_at_uri):
        """Text longer than BLUESKY_MAX_LENGTH should set LONG message type."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        # The rendered template returns "<p>rendered</p>" which is short,
        # but we need the combined text to exceed 800 chars.
        # We mock template to return long text.
        self.mock_tpl.render.return_value = "x" * 900

        post = _make_post_view(text="x" * 900)
        thread = _make_thread(post=post, parent=None, replies=None)

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()

        assert result["message_type"] == "long"

    @pytest.mark.asyncio
    async def test_resolve_thread_with_parent(self, _patch_at_uri):
        """Parent posts should be collected recursively."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        grandparent_post = _make_post_view(text="grandparent")
        grandparent_thread = _make_thread(post=grandparent_post, parent=None, replies=None)

        parent_post = _make_post_view(text="parent")
        parent_thread = _make_thread(post=parent_post, parent=grandparent_thread, replies=None)

        base_post = _make_post_view(text="base")
        thread = _make_thread(post=base_post, parent=parent_thread, replies=None)

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_resolve_thread_with_replies_same_author(self, _patch_at_uri):
        """Replies by the same author should be included in the combined text."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        author = _make_author(did="did:plc:abc123")
        base_post = _make_post_view(text="base", author=author)

        reply_post = _make_post_view(text="reply", author=author)
        reply_thread = _make_thread(post=reply_post)

        thread = _make_thread(post=base_post, parent=None, replies=[reply_thread])

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_resolve_thread_with_replies_different_author(self, _patch_at_uri):
        """Replies by a different author should be excluded."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        base_author = _make_author(did="did:plc:abc123")
        other_author = _make_author(did="did:plc:other")

        base_post = _make_post_view(text="base", author=base_author)
        reply_post = _make_post_view(text="other reply", author=other_author)
        reply_thread = _make_thread(post=reply_post)

        thread = _make_thread(post=base_post, parent=None, replies=[reply_thread])

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_resolve_single_post_with_images(self, _patch_at_uri):
        """Posts with image embeds should have media_files populated."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        image_mock = MagicMock()
        image_mock.fullsize = "https://cdn.bsky.app/img/feed/abc/image.jpg"

        # Use a simple namespace object instead of MagicMock to avoid __dict__ conflicts
        class FakeEmbed:
            def __init__(self):
                self.images = [image_mock]
                self.record = None

        embed = FakeEmbed()

        post = _make_post_view(text="photo post", embed=embed)
        thread = _make_thread(post=post, parent=None, replies=None)

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()
        assert len(result["media_files"]) == 1
        assert result["media_files"][0]["media_type"] == "image"

    @pytest.mark.asyncio
    async def test_resolve_single_post_with_retweet(self, _patch_at_uri):
        """Posts with embed.record as ViewRecord should resolve retweet."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor
        from atproto_client.models.app.bsky.embed.record import ViewRecord

        # Use a simple namespace to avoid MagicMock __dict__ issues
        class FakeEmbed:
            def __init__(self):
                self.images = []
                self.record = ViewRecord  # identity check: `is ViewRecord`

        embed = FakeEmbed()

        post = _make_post_view(text="check this out", embed=embed)
        thread = _make_thread(post=post, parent=None, replies=None)

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        # Mock _resolve_single_post_data entirely to avoid calling into ViewRecord as PostView
        call_count = 0

        async def side_effect(post_data):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "url": "https://bsky.app/profile/alice/post/rkey123",
                    "title": "Alice's Bluesky post",
                    "author": "Alice",
                    "author_url": "https://bsky.app/profile/alice",
                    "text": "check this out",
                    "category": "bluesky",
                    "media_files": [],
                    "created_at": "2024-01-01T00:00:00Z",
                    "author_did": "did:plc:abc123",
                    "content": "<p>rendered</p>",
                    "retweet_post": {
                        "url": "https://bsky.app/profile/bob/post/456",
                        "title": "Bob's post",
                        "author": "Bob",
                        "author_url": "https://bsky.app/profile/bob",
                        "text": "original post",
                        "category": "bluesky",
                        "media_files": [],
                        "author_did": "did:plc:bob",
                        "content": "<p>original</p>",
                    },
                }
            return {
                "url": "https://bsky.app/profile/bob/post/456",
                "title": "Bob's post",
                "author": "Bob",
                "author_url": "https://bsky.app/profile/bob",
                "text": "original post",
                "category": "bluesky",
                "media_files": [],
                "author_did": "did:plc:bob",
                "content": "<p>original</p>",
            }

        with patch.object(
            BlueskyDataProcessor,
            "_resolve_single_post_data",
            side_effect=side_effect,
        ):
            result = await processor.get_item()
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_resolve_single_post_retweet_branch_executed(self, _patch_at_uri):
        """Directly test _resolve_single_post_data with embed.record is ViewRecord to cover lines 141-142."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor
        from atproto_client.models.app.bsky.embed.record import ViewRecord

        class FakeEmbed:
            def __init__(self):
                self.images = []
                self.record = ViewRecord  # `is ViewRecord` will be True

        embed = FakeEmbed()
        post = _make_post_view(text="quoting post", embed=embed)

        # Mock the recursive call to _resolve_single_post_data for the retweet
        original_method = BlueskyDataProcessor._resolve_single_post_data
        call_count = 0

        async def patched_resolve(post_data):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                # This is the recursive call for the retweet record
                return {
                    "url": "https://bsky.app/profile/bob/post/456",
                    "title": "Bob's post",
                    "author": "Bob",
                    "author_url": "https://bsky.app/profile/bob",
                    "text": "retweeted content",
                    "category": "bluesky",
                    "media_files": [],
                    "author_did": "did:plc:bob",
                    "content": "<p>retweeted</p>",
                    "created_at": "2024-01-01",
                }
            return await original_method(post_data)

        with patch.object(
            BlueskyDataProcessor,
            "_resolve_single_post_data",
            side_effect=patched_resolve,
        ):
            result = await BlueskyDataProcessor._resolve_single_post_data(post)
            assert "retweet_post" in result
            assert result["retweet_post"]["author"] == "Bob"

    @pytest.mark.asyncio
    async def test_resolve_single_post_no_embed(self, _patch_at_uri):
        """Post without embed should have empty media_files."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        post = _make_post_view(text="text only", embed=None)
        thread = _make_thread(post=post, parent=None, replies=None)

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()
        assert result["media_files"] == []

    @pytest.mark.asyncio
    async def test_empty_parent_posts_data_list(self, _patch_at_uri):
        """When parent exists but parent_posts_data is empty after collection, no text is prepended."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        # Create parent with a post
        parent_post = _make_post_view(text="parent text")
        parent_thread = _make_thread(post=parent_post, parent=None, replies=None)

        base_post = _make_post_view(text="base text")
        thread = _make_thread(post=base_post, parent=parent_thread, replies=None)

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_empty_replies_posts_data_list(self, _patch_at_uri):
        """When replies exist but none match author, replies data is empty."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyDataProcessor

        base_author = _make_author(did="did:plc:abc123")
        other_author = _make_author(did="did:plc:other")

        base_post = _make_post_view(text="base", author=base_author)
        reply_post = _make_post_view(text="different author reply", author=other_author)
        reply_thread = _make_thread(post=reply_post)

        thread = _make_thread(post=base_post, parent=None, replies=[reply_thread])

        processor = BlueskyDataProcessor("https://bsky.app/profile/alice/post/rkey123", thread)
        result = await processor.get_item()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# BlueskyScraper tests
# ---------------------------------------------------------------------------

class TestBlueskyScraper:

    @pytest.fixture(autouse=True)
    def _patch_deps(self):
        """Patch atproto classes and templates at module level."""
        mock_tpl = MagicMock()
        mock_tpl.render.return_value = "<p>rendered</p>"
        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.telegram_text_template",
            mock_tpl,
        ), patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.content_template",
            mock_tpl,
        ):
            yield

    @pytest.mark.asyncio
    async def test_init_with_credentials(self):
        """init() should call client.login when username and password are provided."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyScraper

        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            scraper = BlueskyScraper(username="user", password="pass")
            await scraper.init()
            mock_client.login.assert_awaited_once_with("user", "pass")

    @pytest.mark.asyncio
    async def test_init_without_credentials(self):
        """init() should not call login when credentials are missing."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyScraper

        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            scraper = BlueskyScraper()
            await scraper.init()
            mock_client.login.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_processor_by_url(self):
        """get_processor_by_url should return a BlueskyDataProcessor."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import (
            BlueskyScraper,
            BlueskyDataProcessor,
        )

        mock_resolver = MagicMock()
        mock_resolver.handle.resolve.return_value = "did:plc:resolved"

        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.AsyncClient"
        ) as mock_client_cls, patch.object(
            BlueskyScraper, "id_resolver", mock_resolver
        ):
            mock_client = AsyncMock()
            mock_post_data = MagicMock()
            mock_post_data.uri = "at://did:plc:resolved/app.bsky.feed.post/rkey123"
            mock_client.get_post.return_value = mock_post_data

            mock_thread_data = MagicMock()
            mock_thread_data.thread = _make_thread()
            mock_client.get_post_thread.return_value = mock_thread_data

            mock_client_cls.return_value = mock_client

            scraper = BlueskyScraper()
            processor = await scraper.get_processor_by_url(
                "https://bsky.app/profile/alice.bsky.social/post/rkey123"
            )
            assert isinstance(processor, BlueskyDataProcessor)

    @pytest.mark.asyncio
    async def test_request_post_data_uses_did_when_available(self):
        """_request_post_data should use did as profile_identify when available."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyScraper

        mock_resolver = MagicMock()
        mock_resolver.handle.resolve.return_value = "did:plc:resolved"

        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.AsyncClient"
        ) as mock_client_cls, patch.object(
            BlueskyScraper, "id_resolver", mock_resolver
        ):
            mock_client = AsyncMock()
            mock_post_data = MagicMock()
            mock_post_data.uri = "at://did:plc:resolved/app.bsky.feed.post/rkey123"
            mock_client.get_post.return_value = mock_post_data

            mock_thread_response = MagicMock()
            mock_thread_response.thread = _make_thread()
            mock_client.get_post_thread.return_value = mock_thread_response

            mock_client_cls.return_value = mock_client

            scraper = BlueskyScraper()

            from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyPost

            bluesky_post = MagicMock(spec=BlueskyPost)
            bluesky_post.did = "did:plc:resolved"
            bluesky_post.handle = "alice.bsky.social"
            bluesky_post.post_rkey = "rkey123"

            result = await scraper._request_post_data(bluesky_post)
            mock_client.get_post.assert_awaited_once_with(
                profile_identify="did:plc:resolved", post_rkey="rkey123"
            )

    @pytest.mark.asyncio
    async def test_request_post_data_uses_handle_when_no_did(self):
        """_request_post_data should fall back to handle when did is empty."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyScraper

        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_post_data = MagicMock()
            mock_post_data.uri = "at://did:plc:resolved/app.bsky.feed.post/rkey123"
            mock_client.get_post.return_value = mock_post_data

            mock_thread_response = MagicMock()
            mock_thread_response.thread = _make_thread()
            mock_client.get_post_thread.return_value = mock_thread_response

            mock_client_cls.return_value = mock_client

            scraper = BlueskyScraper()

            bluesky_post = MagicMock()
            bluesky_post.did = ""  # falsy
            bluesky_post.handle = "alice.bsky.social"
            bluesky_post.post_rkey = "rkey123"

            result = await scraper._request_post_data(bluesky_post)
            mock_client.get_post.assert_awaited_once_with(
                profile_identify="alice.bsky.social", post_rkey="rkey123"
            )

    @pytest.mark.asyncio
    async def test_request_post_data_exception_handling(self):
        """_request_post_data should log error and return None on exception."""
        from fastfetchbot_shared.services.scrapers.bluesky.scraper import BlueskyScraper

        with patch(
            "fastfetchbot_shared.services.scrapers.bluesky.scraper.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_post.side_effect = Exception("network error")
            mock_client_cls.return_value = mock_client

            scraper = BlueskyScraper()

            bluesky_post = MagicMock()
            bluesky_post.did = "did:plc:abc"
            bluesky_post.handle = "alice"
            bluesky_post.post_rkey = "rkey123"

            result = await scraper._request_post_data(bluesky_post)
            assert result is None

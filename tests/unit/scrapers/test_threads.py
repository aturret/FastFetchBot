"""Unit tests for Threads scraper module.

Covers:
- packages/shared/fastfetchbot_shared/services/scrapers/threads/__init__.py
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.services.scrapers.threads import Threads


# ---------------------------------------------------------------------------
# Helper to build thread data dicts matching parse_single_threads_data output
# ---------------------------------------------------------------------------

# NOTE: Threads.__init__ extracts code via urlparse(url).path.split("/")[2]
# For URL "https://www.threads.net/@user/post/ABC123", path is "/@user/post/ABC123"
# split("/") = ["", "@user", "post", "ABC123"] -> index 2 = "post"
# So self.code == "post" for standard Threads URLs.

SELF_CODE = "post"  # What self.code resolves to for standard URLs


def _make_thread(
    code="SOMEOTHER",
    username="testuser",
    text="Hello world",
    published_on=1700000000,
    reply_count=5,
    like_count=10,
    image=None,
    video=None,
    media_count=None,
    media_files=None,
    link=None,
    quoted_post=None,
):
    return {
        "text": text,
        "published_on": published_on,
        "id": "id_1",
        "pk": "pk_1",
        "code": code,
        "username": username,
        "user_pic": "http://pic.jpg",
        "user_verified": False,
        "user_pk": "upk",
        "user_id": "uid",
        "has_audio": False,
        "reply_count": reply_count,
        "like_count": like_count,
        "media_files": media_files,
        "images": None,
        "image": image,
        "video": video,
        "media_count": media_count,
        "quoted_post": quoted_post,
        "link": link,
    }


class TestThreadsInit:
    """Tests for Threads.__init__."""

    def test_default_init(self):
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        assert t.url == "https://www.threads.net/@user/post/ABC123"
        assert t.code == "post"
        assert t.title == ""
        assert t.author == ""
        assert t.category == "threads"
        assert t.message_type == MessageType.SHORT
        assert t.pics_url == []
        assert t.videos_url == []
        assert t.media_files == []
        assert t.text_group == ""
        assert t.content_group == ""

    def test_init_with_data_kwarg(self):
        """data and kwargs are accepted but not used."""
        t = Threads(url="https://www.threads.net/@user/post/XYZ", data={"k": "v"})
        assert t.code == "post"

    def test_code_extraction_different_path(self):
        """Different URL structures give different codes."""
        t = Threads(url="https://www.threads.net/t/CuXFPIeLLqr")
        # path = "/t/CuXFPIeLLqr" -> split("/") = ["", "t", "CuXFPIeLLqr"]
        assert t.code == "CuXFPIeLLqr"


class TestParseSingleThreadsData:
    """Tests for Threads.parse_single_threads_data (static)."""

    def test_parses_basic_fields(self):
        data = {
            "caption": {"text": "Test caption"},
            "taken_at": 1700000000,
            "id": "123",
            "pk": "456",
            "code": "ABC",
            "user": {
                "username": "testuser",
                "profile_pic_url": "http://pic.jpg",
                "is_verified": True,
                "pk": "upk",
                "id": "uid",
            },
            "has_audio": False,
            "text_post_app_info": {
                "direct_reply_count": 3,
                "share_info": {"quoted_post": None},
                "link_preview_attachment": None,
            },
            "like_count": 10,
            "carousel_media": None,
            "carousel_media_count": None,
            "image_versions2": {"candidates": [None, {"url": "http://img.jpg"}]},
            "video_versions": None,
        }
        result = Threads.parse_single_threads_data(data)
        assert result["text"] == "Test caption"
        assert result["username"] == "testuser"
        assert result["code"] == "ABC"
        assert result["image"] == "http://img.jpg"
        assert result["like_count"] == 10
        assert result["reply_count"] == 3

    def test_missing_fields_returns_none(self):
        result = Threads.parse_single_threads_data({})
        assert result["text"] is None
        assert result["username"] is None
        assert result["code"] is None


class TestParseSingleThreads:
    """Tests for Threads.parse_single_threads (static)."""

    def test_single_image_no_media_count(self):
        thread = _make_thread(image="http://img.jpg")
        result = Threads.parse_single_threads(thread)
        assert len(result["pics_url"]) == 1
        assert result["pics_url"][0] == "http://img.jpg"
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "image"
        assert '<img src="http://img.jpg">' in result["content_group"]

    def test_single_video_no_media_count(self):
        thread = _make_thread(video="http://vid.mp4")
        result = Threads.parse_single_threads(thread)
        assert len(result["videos_url"]) == 1
        assert result["videos_url"][0] == "http://vid.mp4"
        assert result["media_files"][0].media_type == "video"
        assert "video" in result["content_group"]

    def test_no_media(self):
        thread = _make_thread()
        result = Threads.parse_single_threads(thread)
        assert len(result["pics_url"]) == 0
        assert len(result["videos_url"]) == 0
        assert len(result["media_files"]) == 0

    def test_multiple_media_with_images(self):
        media = [
            {
                "video_versions": [],
                "image_versions2": {
                    "candidates": [{"url": "http://img1.jpg"}]
                },
            },
            {
                "video_versions": [],
                "image_versions2": {
                    "candidates": [{"url": "http://img2.jpg"}]
                },
            },
        ]
        thread = _make_thread(media_count=2, media_files=media)
        result = Threads.parse_single_threads(thread)
        assert len(result["pics_url"]) == 2
        assert len(result["media_files"]) == 2
        assert all(mf.media_type == "image" for mf in result["media_files"])

    def test_multiple_media_with_videos(self):
        media = [
            {
                "video_versions": [{"url": "http://vid1.mp4"}],
                "image_versions2": {"candidates": [{"url": "http://thumb.jpg"}]},
            },
        ]
        thread = _make_thread(media_count=1, media_files=media)
        result = Threads.parse_single_threads(thread)
        assert len(result["videos_url"]) == 1
        assert result["media_files"][0].media_type == "video"
        assert "video" in result["content_group"]

    def test_multiple_media_mixed(self):
        media = [
            {
                "video_versions": [{"url": "http://vid1.mp4"}],
                "image_versions2": {"candidates": [{"url": "http://thumb.jpg"}]},
            },
            {
                "video_versions": [],
                "image_versions2": {"candidates": [{"url": "http://img1.jpg"}]},
            },
        ]
        thread = _make_thread(media_count=2, media_files=media)
        result = Threads.parse_single_threads(thread)
        assert len(result["videos_url"]) == 1
        assert len(result["pics_url"]) == 1

    def test_with_link(self):
        link = {
            "title": "Link Title",
            "url": f"https://l.threads.net/redirect?url={quote('https://example.com')}&other=val",
        }
        thread = _make_thread(link=link)
        result = Threads.parse_single_threads(thread)
        assert "Link Title" in result["text_group"]
        assert "https://example.com" in result["content_group"]

    def test_without_link(self):
        thread = _make_thread(link=None)
        result = Threads.parse_single_threads(thread)
        assert "<hr>" in result["content_group"]

    def test_with_quoted_post(self):
        """Test retweeted (quoted) post processing."""
        quoted_data = {
            "caption": {"text": "Quoted text"},
            "taken_at": 1700000000,
            "id": "q1",
            "pk": "qpk",
            "code": "QCODE",
            "user": {
                "username": "quoteduser",
                "profile_pic_url": "http://qpic.jpg",
                "is_verified": False,
                "pk": "qupk",
                "id": "quid",
            },
            "has_audio": False,
            "text_post_app_info": {
                "direct_reply_count": 0,
                "share_info": {"quoted_post": None},
                "link_preview_attachment": None,
            },
            "like_count": 2,
            "carousel_media": None,
            "carousel_media_count": None,
            "image_versions2": None,
            "video_versions": None,
        }
        thread = _make_thread(quoted_post=quoted_data)
        result = Threads.parse_single_threads(thread)
        # Should include content from both the main thread and the quoted post
        assert "quoteduser" in result["content_group"]
        assert "testuser" in result["content_group"]

    def test_without_quoted_post(self):
        thread = _make_thread(quoted_post=None)
        result = Threads.parse_single_threads(thread)
        assert isinstance(result["content_group"], str)

    def test_content_group_has_hr(self):
        thread = _make_thread()
        result = Threads.parse_single_threads(thread)
        assert "<hr>" in result["content_group"]

    def test_text_group_includes_username(self):
        thread = _make_thread(username="myuser", text="My post")
        result = Threads.parse_single_threads(thread)
        assert "@myuser" in result["text_group"]
        assert "My post" in result["text_group"]


class TestProcessSingleThreads:
    """Tests for Threads.process_single_threads."""

    def test_authoral_post(self):
        """Thread matching self.code sets title, author, metadata."""
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        # self.code == "post", so use code="post" for the authoral thread
        thread = _make_thread(
            code=SELF_CODE,
            username="user",
            reply_count=5,
            like_count=10,
            published_on=1700000000,
        )
        t.process_single_threads(thread)
        assert t.title == "user's Threads"
        assert t.author == "user"
        assert "https://threads.net/@user" in t.author_url
        assert "Reply count: 5" in t.content
        assert "Like count: 10" in t.content
        assert "Created at:" in t.content

    def test_non_authoral_post(self):
        """Thread not matching self.code doesn't set title/author."""
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        thread = _make_thread(code="OTHER", username="other")
        t.process_single_threads(thread)
        assert t.title == ""
        assert t.author == ""

    def test_accumulates_media(self):
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        thread = _make_thread(code=SELF_CODE, image="http://img.jpg")
        t.process_single_threads(thread)
        assert len(t.pics_url) == 1
        assert len(t.media_files) == 1


class TestProcessThreadsItem:
    """Tests for Threads.process_threads_item."""

    def test_processes_multiple_threads(self):
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        thread_data = {
            "threads": [
                _make_thread(code=SELF_CODE, username="user", text="Main post"),
                _make_thread(code="REPLY1", username="replier", text="Reply"),
            ]
        }
        t.process_threads_item(thread_data)
        assert t.title == "user's Threads"
        assert "Main post" in t.text
        assert "Reply" in t.text

    def test_short_message_type(self):
        """Short text results in SHORT message type."""
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        thread_data = {
            "threads": [
                _make_thread(code=SELF_CODE, username="u", text="short"),
            ]
        }
        t.process_threads_item(thread_data)
        assert t.message_type == MessageType.SHORT

    def test_long_message_type(self):
        """Long text results in LONG message type."""
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        long_text = "x" * 700
        thread_data = {
            "threads": [
                _make_thread(code=SELF_CODE, username="u", text=long_text),
            ]
        }
        t.process_threads_item(thread_data)
        assert t.message_type == MessageType.LONG

    def test_empty_threads(self):
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        thread_data = {"threads": []}
        t.process_threads_item(thread_data)
        assert t.text == ""
        assert t.content == ""


class TestScrapeThreadData:
    """Tests for Threads.scrape_thread_data with fully mocked playwright."""

    @pytest.mark.asyncio
    async def test_scrape_with_single_gql_call(self):
        gql_response_data = {
            "data": {
                "data": {
                    "containing_thread": {
                        "thread_items": [
                            {
                                "post": {
                                    "caption": {"text": "Scraped text"},
                                    "taken_at": 1700000000,
                                    "id": "1",
                                    "pk": "1",
                                    "code": "ABC123",
                                    "user": {
                                        "username": "scraped_user",
                                        "profile_pic_url": "http://p.jpg",
                                        "is_verified": False,
                                        "pk": "1",
                                        "id": "1",
                                    },
                                    "has_audio": False,
                                    "text_post_app_info": {
                                        "direct_reply_count": 0,
                                        "share_info": {"quoted_post": None},
                                        "link_preview_attachment": None,
                                    },
                                    "like_count": 5,
                                    "carousel_media": None,
                                    "carousel_media_count": None,
                                    "image_versions2": None,
                                    "video_versions": None,
                                }
                            }
                        ]
                    }
                }
            }
        }

        # Build mock playwright chain
        mock_response_xhr = AsyncMock()
        mock_response_xhr.request.resource_type = "xhr"
        mock_response_xhr.url = "https://www.threads.net/api/graphql"
        mock_response_xhr.text = AsyncMock(return_value=json.dumps(gql_response_data))

        mock_response_other = AsyncMock()
        mock_response_other.request.resource_type = "document"

        mock_page = AsyncMock()
        # Capture the on callback
        response_callback = None

        def mock_on(event, callback):
            nonlocal response_callback
            response_callback = callback

        mock_page.on = mock_on
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw = AsyncMock()
        mock_pw.chromium = mock_chromium

        mock_pw_ctx = AsyncMock()
        mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.threads.async_playwright",
            return_value=mock_pw_ctx,
        ):
            t = Threads(url="https://www.threads.net/@user/post/ABC123")

            # Simulate the page.goto triggering the intercept
            async def simulate_goto(url):
                await response_callback(mock_response_xhr)
                await response_callback(mock_response_other)

            mock_page.goto = simulate_goto

            result = await t.scrape_thread_data("https://www.threads.net/@user/post/ABC123")

        assert "threads" in result
        assert len(result["threads"]) == 1
        assert result["threads"][0]["text"] == "Scraped text"
        assert result["threads"][0]["username"] == "scraped_user"

    @pytest.mark.asyncio
    async def test_scrape_no_gql_calls(self):
        """When no graphql XHR calls are captured, result has empty threads."""
        mock_page = AsyncMock()
        mock_page.on = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw = AsyncMock()
        mock_pw.chromium = mock_chromium

        mock_pw_ctx = AsyncMock()
        mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.services.scrapers.threads.async_playwright",
            return_value=mock_pw_ctx,
        ):
            t = Threads(url="https://www.threads.net/@user/post/ABC123")
            result = await t.scrape_thread_data("https://www.threads.net/@user/post/ABC123")

        assert result == {"threads": []}


class TestGetThreads:
    """Tests for Threads.get_threads."""

    @pytest.mark.asyncio
    async def test_get_threads_full_flow(self):
        thread_data = {
            "threads": [
                _make_thread(code=SELF_CODE, username="user", text="Post text"),
            ]
        }
        with patch.object(
            Threads, "scrape_thread_data", new_callable=AsyncMock, return_value=thread_data
        ):
            t = Threads(url="https://www.threads.net/@user/post/ABC123")
            await t.get_threads()
        assert t.title == "user's Threads"
        assert "Post text" in t.text


class TestGetItem:
    """Tests for Threads.get_item."""

    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self):
        thread_data = {
            "threads": [
                _make_thread(code=SELF_CODE, username="user", text="Item text"),
            ]
        }
        with patch.object(
            Threads, "scrape_thread_data", new_callable=AsyncMock, return_value=thread_data
        ):
            t = Threads(url="https://www.threads.net/@user/post/ABC123")
            result = await t.get_item()
        assert isinstance(result, dict)
        assert result["title"] == "user's Threads"
        assert result["author"] == "user"
        assert result["category"] == "threads"
        assert "url" in result
        assert "content" in result
        assert "text" in result
        assert "media_files" in result


class TestEdgeCases:
    """Edge cases and branch coverage."""

    def test_link_url_parsing(self):
        """Test link URL extraction from threads link object."""
        link = {
            "title": "My Link",
            "url": "https://l.threads.net/redirect?url=https%3A%2F%2Fexample.com%2Fpage&tracking=abc",
        }
        thread = _make_thread(link=link)
        result = Threads.parse_single_threads(thread)
        assert "example.com" in result["content_group"]

    def test_multiple_media_video_and_image(self):
        """Mixed carousel with both video and image entries."""
        media = [
            {
                "video_versions": [{"url": "http://vid.mp4"}],
                "image_versions2": {"candidates": [{"url": "http://thumb.jpg"}]},
            },
            {
                "video_versions": [],
                "image_versions2": {"candidates": [{"url": "http://photo.jpg"}]},
            },
        ]
        thread = _make_thread(media_count=2, media_files=media)
        result = Threads.parse_single_threads(thread)
        assert len(result["videos_url"]) == 1
        assert len(result["pics_url"]) == 1
        assert len(result["media_files"]) == 2

    def test_process_single_threads_accumulates_to_groups(self):
        """process_single_threads adds to text_group and content_group."""
        t = Threads(url="https://www.threads.net/@user/post/ABC123")
        t.process_single_threads(_make_thread(code=SELF_CODE, username="u", text="t1"))
        t.process_single_threads(_make_thread(code="OTHER", username="u2", text="t2"))
        assert "t1" in t.text_group
        assert "t2" in t.text_group
        assert "u" in t.content_group
        assert "u2" in t.content_group

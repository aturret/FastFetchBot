"""Unit tests for Instagram scraper and config modules.

Covers:
- packages/shared/fastfetchbot_shared/services/scrapers/instagram/__init__.py
- packages/shared/fastfetchbot_shared/services/scrapers/instagram/config.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastfetchbot_shared.services.scrapers.instagram.config import (
    API_HEADERS_LIST,
    ALL_SCRAPERS,
)
from fastfetchbot_shared.services.scrapers.instagram import Instagram
from fastfetchbot_shared.models.metadata_item import MessageType, MediaFile

# Patch target for get_response at the Instagram module level (where it was imported via `from ... import`)
_PATCH_GET_RESPONSE = "fastfetchbot_shared.services.scrapers.instagram.get_response"


@pytest.fixture
def mock_ig_get_response():
    """Patch get_response at the Instagram module level."""
    with patch(_PATCH_GET_RESPONSE, new_callable=AsyncMock) as m:
        yield m


# ---------------------------------------------------------------------------
# config.py tests
# ---------------------------------------------------------------------------

class TestInstagramConfig:
    """Tests for instagram/config.py constants."""

    def test_all_scrapers_is_list(self):
        assert isinstance(ALL_SCRAPERS, list)
        assert len(ALL_SCRAPERS) > 0

    def test_all_scrapers_contents(self):
        assert ALL_SCRAPERS == ["ins28", "scraper2", "looter2", "ins191", "ins130"]

    def test_api_headers_list_is_dict(self):
        assert isinstance(API_HEADERS_LIST, dict)

    def test_api_headers_list_keys(self):
        expected = {"looter2", "ins28", "scraper2", "ins191", "ins130", "api2"}
        assert set(API_HEADERS_LIST.keys()) == expected

    def test_each_scraper_has_required_keys(self):
        for name, entry in API_HEADERS_LIST.items():
            assert "host" in entry, f"{name} missing 'host'"
            assert "top_domain" in entry, f"{name} missing 'top_domain'"
            assert "params" in entry, f"{name} missing 'params'"

    def test_looter2_params_value_is_url(self):
        assert API_HEADERS_LIST["looter2"]["params"] == "url"


# ---------------------------------------------------------------------------
# Instagram class tests
# ---------------------------------------------------------------------------

class TestInstagramInit:
    """Tests for Instagram.__init__."""

    def test_init_post_url(self):
        url = "https://www.instagram.com/p/ABC123/"
        ig = Instagram(url)
        assert ig.url == url
        assert ig.category == "instagram"
        assert ig.post_id == "ABC123"
        assert ig.message_type == MessageType.SHORT

    def test_init_reel_url(self):
        url = "https://www.instagram.com/reel/XYZ789/"
        ig = Instagram(url)
        assert ig.post_id == "XYZ789"

    def test_init_with_data_kwarg(self):
        ig = Instagram("https://www.instagram.com/p/TEST/", data={"key": "val"})
        assert ig.post_id == "TEST"


class TestCheckInstagramUrl:
    """Tests for Instagram._check_instagram_url."""

    def test_post_url(self):
        ig = Instagram("https://www.instagram.com/p/ABC123/")
        ig._check_instagram_url()
        assert ig.ins_type == "post"

    def test_reel_url(self):
        ig = Instagram("https://www.instagram.com/reel/ABC123/")
        ig._check_instagram_url()
        assert ig.ins_type == "post"  # "reel" path also contains no "stories"

    def test_story_url(self):
        ig = Instagram("https://www.instagram.com/stories/user/12345/")
        ig._check_instagram_url()
        assert ig.ins_type == "story"

    def test_story_overrides_post(self):
        """Path with both 'p' and 'stories' should end up as 'story'."""
        ig = Instagram("https://www.instagram.com/stories/p/12345/")
        ig._check_instagram_url()
        assert ig.ins_type == "story"


class TestGetStoryInfo:
    """Tests for Instagram._get_story_info."""

    @pytest.mark.asyncio
    async def test_get_story_info_returns_none(self):
        ig = Instagram("https://www.instagram.com/stories/user/1/")
        result = await ig._get_story_info()
        assert result is None


class TestGetInsPostLooter2:
    """Tests for Instagram._get_ins_post_looter2 — static method."""

    def _make_base_data(self, typename, **overrides):
        data = {
            "edge_media_to_caption": {"edges": [{"node": {"text": "caption text"}}]},
            "owner": {"username": "testuser", "full_name": "Test User"},
            "__typename": typename,
        }
        data.update(overrides)
        return data

    def test_graph_video(self):
        data = self._make_base_data("GraphVideo", video_url="https://vid.com/v.mp4")
        result = Instagram._get_ins_post_looter2(data)
        assert result["status"] is True
        assert result["author"] == "testuser(Test User)"
        assert result["text"] == "caption text"
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "video"
        assert "video" in result["content"]

    def test_graph_image(self):
        data = self._make_base_data("GraphImage", display_url="https://img.com/i.jpg")
        result = Instagram._get_ins_post_looter2(data)
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "image"
        assert "img" in result["content"]

    def test_graph_image_no_display_url(self):
        data = self._make_base_data("GraphImage", display_url="")
        result = Instagram._get_ins_post_looter2(data)
        assert result["media_files"][0].url == ""
        # content should not have img tag when display_url is empty
        assert "<img" not in result["content"].split("caption text")[0]

    def test_graph_sidecar_mixed(self):
        data = self._make_base_data("GraphSidecar")
        data["edge_sidecar_to_children"] = {
            "edges": [
                {"node": {"__typename": "GraphVideo", "video_url": "https://v.mp4"}},
                {"node": {"__typename": "GraphImage", "display_url": "https://i.jpg"}},
            ]
        }
        result = Instagram._get_ins_post_looter2(data)
        assert len(result["media_files"]) == 2
        assert result["media_files"][0].media_type == "video"
        assert result["media_files"][1].media_type == "image"

    def test_empty_caption(self):
        data = {
            "edge_media_to_caption": {"edges": []},
            "owner": {"username": "u", "full_name": ""},
            "__typename": "GraphImage",
            "display_url": "https://img.com/i.jpg",
        }
        result = Instagram._get_ins_post_looter2(data)
        assert result["text"] == ""
        # author without full_name should not have parentheses
        assert result["author"] == "u"

    def test_no_full_name(self):
        data = self._make_base_data("GraphImage", display_url="https://img.com/i.jpg")
        data["owner"]["full_name"] = ""
        result = Instagram._get_ins_post_looter2(data)
        assert "(" not in result["author"]


class TestGetInsPostIns28Scraper2:
    """Tests for Instagram._get_ins_post_ins28_scraper2 — static method."""

    def _make_base_data(self, media_type, **item_overrides):
        item = {
            "caption": {"text": "ins28 caption"},
            "user": {"username": "u28", "full_name": "User28"},
            "media_type": media_type,
        }
        item.update(item_overrides)
        return {"items": [item]}

    def test_video_media_type_2(self):
        data = self._make_base_data(2, video_versions=[{"url": "https://v.mp4"}])
        result = Instagram._get_ins_post_ins28_scraper2(data)
        assert result["status"] is True
        assert result["author"] == "u28(User28)"
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "video"

    def test_image_media_type_1(self):
        data = self._make_base_data(
            1,
            image_versions2={"candidates": [{"url": "https://img.jpg"}]},
        )
        result = Instagram._get_ins_post_ins28_scraper2(data)
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "image"

    def test_carousel_media_type_8(self):
        data = self._make_base_data(8)
        data["items"][0]["carousel_media"] = [
            {"media_type": 2, "video_versions": [{"url": "https://v.mp4"}]},
            {
                "media_type": 1,
                "image_versions2": {"candidates": [{"url": "https://img.jpg"}]},
            },
        ]
        result = Instagram._get_ins_post_ins28_scraper2(data)
        assert len(result["media_files"]) == 2

    def test_no_caption(self):
        data = self._make_base_data(
            1,
            image_versions2={"candidates": [{"url": "https://img.jpg"}]},
        )
        data["items"][0]["caption"] = None
        result = Instagram._get_ins_post_ins28_scraper2(data)
        assert result["text"] == ""

    def test_no_full_name(self):
        data = self._make_base_data(
            1,
            image_versions2={"candidates": [{"url": "https://img.jpg"}]},
        )
        data["items"][0]["user"]["full_name"] = ""
        result = Instagram._get_ins_post_ins28_scraper2(data)
        assert "(" not in result["author"]


class TestProcessInsInfo:
    """Tests for Instagram._process_ins_info."""

    def test_short_text(self):
        ig = Instagram("https://www.instagram.com/p/X/")
        ig._process_ins_info(
            {
                "author": "joe",
                "text": "hello",
                "media_files": [],
                "content": "",
                "status": True,
            }
        )
        assert ig.title == "joe's Instagram post"
        assert ig.message_type == MessageType.SHORT
        assert "hello" in ig.text

    def test_long_text_switches_message_type(self):
        ig = Instagram("https://www.instagram.com/p/X/")
        long_text = "a" * 600
        ig._process_ins_info(
            {
                "author": "joe",
                "text": long_text,
                "media_files": [],
                "content": "",
                "status": True,
            }
        )
        assert ig.message_type == MessageType.LONG

    def test_html_escaping(self):
        ig = Instagram("https://www.instagram.com/p/X/")
        ig._process_ins_info(
            {
                "author": "joe",
                "text": "<script>alert(1)</script>",
                "media_files": [],
                "content": "",
                "status": True,
            }
        )
        assert "<script>" not in ig.text
        assert "&lt;script&gt;" in ig.text


class TestGetPostInfo:
    """Tests for Instagram._get_post_info — exercises the scraper loop."""

    @pytest.mark.asyncio
    async def test_first_scraper_succeeds_looter2_format(self, mock_ig_get_response):
        """ins28 is first in ALL_SCRAPERS; uses _get_ins_post_ins28_scraper2."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "caption": {"text": "hi"},
                    "user": {"username": "u", "full_name": "U"},
                    "media_type": 1,
                    "image_versions2": {"candidates": [{"url": "https://img.jpg"}]},
                }
            ]
        }
        mock_ig_get_response.return_value = mock_resp

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        result = await ig._get_post_info()
        assert result["status"] is True
        assert mock_ig_get_response.call_count == 1

    @pytest.mark.asyncio
    async def test_non_200_skips_scraper(self, mock_ig_get_response):
        """Non-200 status causes the loop to try the next scraper."""
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "items": [
                {
                    "caption": {"text": "ok"},
                    "user": {"username": "u", "full_name": ""},
                    "media_type": 1,
                    "image_versions2": {"candidates": [{"url": "https://img.jpg"}]},
                }
            ]
        }
        mock_ig_get_response.side_effect = [fail_resp, ok_resp]

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        result = await ig._get_post_info()
        assert result["status"] is True
        assert mock_ig_get_response.call_count == 2

    @pytest.mark.asyncio
    async def test_graphql_format_detected(self, mock_ig_get_response):
        """Response with 'graphql' key is unwrapped for looter2-style scrapers."""
        # looter2 is third in ALL_SCRAPERS list; first two fail
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "graphql": {
                "shortcode_media": {
                    "edge_media_to_caption": {"edges": [{"node": {"text": "gql"}}]},
                    "owner": {"username": "u", "full_name": ""},
                    "__typename": "GraphImage",
                    "display_url": "https://img.jpg",
                }
            }
        }
        mock_ig_get_response.side_effect = [fail_resp, fail_resp, ok_resp]

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        result = await ig._get_post_info()
        assert result["text"] == "gql"

    @pytest.mark.asyncio
    async def test_data_key_format(self, mock_ig_get_response):
        """Response with 'data' key is unwrapped."""
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "data": {
                "edge_media_to_caption": {"edges": [{"node": {"text": "data_fmt"}}]},
                "owner": {"username": "u", "full_name": ""},
                "__typename": "GraphImage",
                "display_url": "https://img.jpg",
            }
        }
        # Make this hit a looter2/ins191/ins130 scraper (3rd, 4th, or 5th)
        mock_ig_get_response.side_effect = [fail_resp, fail_resp, ok_resp]

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        result = await ig._get_post_info()
        assert result["text"] == "data_fmt"

    @pytest.mark.asyncio
    async def test_status_false_skips(self, mock_ig_get_response):
        """Response with status=False in body causes continue."""
        fail_body_resp = MagicMock()
        fail_body_resp.status_code = 200
        fail_body_resp.json.return_value = {"status": False}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "items": [
                {
                    "caption": {"text": "ok"},
                    "user": {"username": "u", "full_name": ""},
                    "media_type": 1,
                    "image_versions2": {"candidates": [{"url": "https://img.jpg"}]},
                }
            ]
        }
        mock_ig_get_response.side_effect = [fail_body_resp, ok_resp]

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        result = await ig._get_post_info()
        assert result["status"] is True

    @pytest.mark.asyncio
    async def test_string_400_skips(self, mock_ig_get_response):
        """Response that is a string containing '400' causes continue."""
        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.return_value = "Error 400 bad request"

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "items": [
                {
                    "caption": {"text": "ok"},
                    "user": {"username": "u", "full_name": ""},
                    "media_type": 1,
                    "image_versions2": {"candidates": [{"url": "https://img.jpg"}]},
                }
            ]
        }
        mock_ig_get_response.side_effect = [bad_resp, ok_resp]

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        result = await ig._get_post_info()
        assert result["status"] is True

    @pytest.mark.asyncio
    async def test_looter2_uses_url_as_param(self, mock_ig_get_response):
        """When scraper is looter2, the params value should be the full URL."""
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "edge_media_to_caption": {"edges": [{"node": {"text": "hi"}}]},
            "owner": {"username": "u", "full_name": ""},
            "__typename": "GraphImage",
            "display_url": "https://img.jpg",
        }
        # ins28 fails, scraper2 fails, then looter2 succeeds
        mock_ig_get_response.side_effect = [fail_resp, fail_resp, ok_resp]

        url = "https://www.instagram.com/p/ABC/"
        ig = Instagram(url)
        ig._check_instagram_url()
        await ig._get_post_info()
        # 3rd call is for looter2
        third_call = mock_ig_get_response.call_args_list[2]
        assert third_call.kwargs["params"]["url"] == url


class TestGetInstagramInfo:
    """Tests for Instagram._get_instagram_info dispatching."""

    @pytest.mark.asyncio
    async def test_dispatches_to_post(self, mock_ig_get_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "caption": {"text": "cap"},
                    "user": {"username": "u", "full_name": ""},
                    "media_type": 1,
                    "image_versions2": {"candidates": [{"url": "https://img.jpg"}]},
                }
            ]
        }
        mock_ig_get_response.return_value = mock_resp

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        await ig._get_instagram_info()
        assert hasattr(ig, "title")

    @pytest.mark.asyncio
    async def test_dispatches_to_story(self):
        ig = Instagram("https://www.instagram.com/stories/user/1/")
        ig._check_instagram_url()
        # _get_story_info returns None, so _process_ins_info will fail
        # but we verify the dispatch works
        with pytest.raises(TypeError):
            await ig._get_instagram_info()


class TestGetItem:
    """Tests for Instagram.get_item end-to-end."""

    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self, mock_ig_get_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "caption": {"text": "full test"},
                    "user": {"username": "user1", "full_name": "Full Name"},
                    "media_type": 1,
                    "image_versions2": {"candidates": [{"url": "https://img.jpg"}]},
                }
            ]
        }
        mock_ig_get_response.return_value = mock_resp

        ig = Instagram("https://www.instagram.com/p/FULL/")
        result = await ig.get_item()
        assert isinstance(result, dict)
        assert result["category"] == "instagram"
        assert "url" in result
        assert result["message_type"] == "short"


class TestAllScrapersExhausted:
    """Test behavior when all scrapers fail."""

    @pytest.mark.asyncio
    async def test_all_fail_returns_empty_dict(self, mock_ig_get_response):
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        mock_ig_get_response.return_value = fail_resp

        ig = Instagram("https://www.instagram.com/p/ABC/")
        ig._check_instagram_url()
        result = await ig._get_post_info()
        assert result == {}

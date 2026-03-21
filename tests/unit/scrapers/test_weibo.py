"""
Unit tests for the Weibo scraper module.

Covers:
- packages/shared/fastfetchbot_shared/services/scrapers/weibo/__init__.py (Weibo dataclass)
- packages/shared/fastfetchbot_shared/services/scrapers/weibo/scraper.py
  (WeiboDataProcessor, WeiboScraper)
- packages/shared/fastfetchbot_shared/services/scrapers/weibo/config.py

Every code path is exercised: Weibo.from_dict / to_dict, WeiboDataProcessor.__init__,
get_item, process_data, _get_weibo (fallback), _get_weibo_info routing,
_get_weibo_info_webpage, _get_weibo_info_api, _get_long_weibo_info_api,
_process_weibo_item (long/short text, retweeted_status), _parse_weibo_info,
_get_media_files, _get_pictures (pics array, pic_infos dict, live photo, gif),
_get_videos (page_info extraction, fallback keys), _get_mix_media (pic, video,
live_photo, gif types), _string_to_int, _get_live_photo,
_weibo_html_text_clean (bs4/lxml dispatch), _weibo_html_text_clean_bs4,
_weibo_html_text_clean_lxml, WeiboScraper.get_processor_by_url.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Dict

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType


# ---------------------------------------------------------------------------
# config.py tests
# ---------------------------------------------------------------------------

class TestWeiboConfig:
    def test_config_constants(self):
        from fastfetchbot_shared.services.scrapers.weibo.config import (
            AJAX_HOST, AJAX_LONGTEXT_HOST, WEIBO_WEB_HOST, WEIBO_HOST, WEIBO_TEXT_LIMIT,
        )
        assert AJAX_HOST == "https://weibo.com/ajax/statuses/show?id="
        assert AJAX_LONGTEXT_HOST == "https://weibo.com/ajax/statuses/longtext?id="
        assert WEIBO_WEB_HOST == "https://m.weibo.cn/detail/"
        assert WEIBO_HOST == "https://weibo.com"
        assert WEIBO_TEXT_LIMIT == 700


# ---------------------------------------------------------------------------
# Weibo dataclass
# ---------------------------------------------------------------------------

class TestWeiboDataclass:
    def test_from_dict(self):
        from fastfetchbot_shared.services.scrapers.weibo import Weibo
        d = {
            "url": "https://weibo.com/1",
            "telegraph_url": "",
            "content": "<p>c</p>",
            "text": "t",
            "media_files": [],
            "author": "auth",
            "title": "title",
            "author_url": "https://weibo.com/auth",
            "category": "weibo",
            "message_type": "short",
            "id": "12345",
        }
        w = Weibo.from_dict(d)
        assert w.id == "12345"
        assert w.url == "https://weibo.com/1"
        assert w.category == "weibo"

    def test_to_dict(self):
        from fastfetchbot_shared.services.scrapers.weibo import Weibo
        w = Weibo(
            url="https://weibo.com/1",
            telegraph_url="",
            content="c",
            text="t",
            media_files=[],
            author="a",
            title="ti",
            author_url="au",
            category="weibo",
            message_type=MessageType.SHORT,
            id="999",
        )
        d = w.to_dict()
        assert d["id"] == "999"
        assert d["category"] == "weibo"
        assert d["message_type"] == "short"


# ---------------------------------------------------------------------------
# WeiboDataProcessor.__init__
# ---------------------------------------------------------------------------

class TestWeiboDataProcessorInit:
    def test_basic_init(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.get_random_user_agent", return_value="TestAgent"):
                from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
                wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/4900001")
        assert wp.id == "4900001"
        assert wp.url == "https://m.weibo.cn/detail/4900001"
        assert wp.method == "api"
        assert wp.headers["User-Agent"] == "TestAgent"
        assert "4900001" in wp.ajax_url
        assert "4900001" in wp.ajax_longtext_url

    def test_init_with_custom_params(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(
                url="https://m.weibo.cn/detail/123",
                method="webpage",
                user_agent="CustomAgent",
                cookies="custom=cookie",
            )
        assert wp.method == "webpage"
        assert wp.headers["User-Agent"] == "CustomAgent"
        assert wp.headers["Cookie"] == "custom=cookie"

    def test_init_with_no_cookies(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(
                url="https://m.weibo.cn/detail/123",
                cookies=None,
            )
        assert wp.headers["Cookie"] == ""


# ---------------------------------------------------------------------------
# _string_to_int (static)
# ---------------------------------------------------------------------------

class TestStringToInt:
    def test_int_input(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        assert WeiboDataProcessor._string_to_int(42) == 42

    def test_plain_string(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        assert WeiboDataProcessor._string_to_int("100") == 100

    def test_wan_plus(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        assert WeiboDataProcessor._string_to_int("5万+") == 50000

    def test_wan(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        assert WeiboDataProcessor._string_to_int("1.5万") == 15000

    def test_yi(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        assert WeiboDataProcessor._string_to_int("2亿") == 200000000

    def test_yi_float(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        assert WeiboDataProcessor._string_to_int("1.5亿") == 150000000


# ---------------------------------------------------------------------------
# _get_live_photo (static)
# ---------------------------------------------------------------------------

class TestGetLivePhoto:
    def test_with_live_photo(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {"pic_video": "0:abc123,1:def456"}
        result = WeiboDataProcessor._get_live_photo(weibo_info)
        assert len(result) == 2
        assert result[0].endswith(".mov")
        assert "abc123" in result[0]

    def test_no_live_photo(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {}
        result = WeiboDataProcessor._get_live_photo(weibo_info)
        assert result is None

    def test_single_item_without_colon(self):
        """Items without exactly 2 parts after split(':') are skipped."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {"pic_video": "nocolon"}
        result = WeiboDataProcessor._get_live_photo(weibo_info)
        assert result == []

    def test_empty_string(self):
        """Empty string is falsy, so function returns None (no explicit return)."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {"pic_video": ""}
        result = WeiboDataProcessor._get_live_photo(weibo_info)
        assert result is None


# ---------------------------------------------------------------------------
# _weibo_html_text_clean dispatch
# ---------------------------------------------------------------------------

class TestWeiboHtmlTextClean:
    def test_bs4_method(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        result, pics = WeiboDataProcessor._weibo_html_text_clean("<p>Hello</p>", method="bs4")
        assert "Hello" in result

    def test_lxml_method(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        result = WeiboDataProcessor._weibo_html_text_clean("<p>Hello</p>", method="lxml")
        assert "Hello" in result

    def test_invalid_method_raises(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        with pytest.raises(ValueError, match="method must be bs4 or lxml"):
            WeiboDataProcessor._weibo_html_text_clean("<p>test</p>", method="invalid")


# ---------------------------------------------------------------------------
# _weibo_html_text_clean_bs4 (static)
# ---------------------------------------------------------------------------

class TestWeiboHtmlTextCleanBs4:
    def test_img_replaced_with_alt(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<img alt="[smile]" src="https://img.com/smile.png">'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert "[smile]" in result
        assert "<img" not in result

    def test_image_tag_timeline_card_removed(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<image src="https://h5.sinaimg.cn/upload/2015/09/25/3/timeline_card_small_web_default.png">'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert "timeline_card" not in result

    def test_search_link_unwrapped(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<a href="https://m.weibo.cn/search?q=test">test</a>'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert "<a" not in result
        assert "test" in result

    def test_view_image_link_extracted(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<a href="https://img.com/big.jpg">查看图片</a>'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert "https://img.com/big.jpg" in pics

    def test_usercard_link_updated(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<a href="/n/someone" usercard="id=123">@someone</a>'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert 'href="https://weibo.com/n/someone"' in result

    def test_span_unwrapped(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<span class="expand">some text</span>'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert "<span" not in result
        assert "some text" in result

    def test_href_slash_slash_fixed(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<a href="//example.com/path">link</a>'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert 'href="http://example.com/path"' in result

    def test_href_n_slash_fixed(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<a href="/n/user">@user</a>'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        assert 'href="http://weibo.com/n/user"' in result

    def test_image_tag_non_matching_src_kept(self):
        """<image> tags with non-matching src are not removed."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<image src="https://other.com/img.png">'
        result, pics = WeiboDataProcessor._weibo_html_text_clean_bs4(html)
        # bs4 won't special-handle non-matching image tags
        assert pics == []


# ---------------------------------------------------------------------------
# _weibo_html_text_clean_lxml (static)
# ---------------------------------------------------------------------------

class TestWeiboHtmlTextCleanLxml:
    def test_img_replaced_with_alt(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        html = '<div><img alt="emoji" src="https://img.com/e.png">text</div>'
        result = WeiboDataProcessor._weibo_html_text_clean_lxml(html)
        assert "emoji" in result

    def test_plain_text(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        result = WeiboDataProcessor._weibo_html_text_clean_lxml("<p>Simple text</p>")
        assert "Simple text" in result


# ---------------------------------------------------------------------------
# _get_pictures (static)
# ---------------------------------------------------------------------------

class TestGetPictures:
    def test_empty_weibo_info(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        result = WeiboDataProcessor._get_pictures({})
        assert result == []

    def test_pics_array(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pics": [
                {"large": {"url": "https://img.com/1.jpg"}, "type": "normal"},
            ]
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://img.com/1.jpg"
        assert result[0].media_type == "image"

    def test_pics_array_with_livephoto(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pics": [
                {
                    "large": {"url": "https://img.com/1.jpg"},
                    "type": "livephoto",
                    "videoSrc": "https://video.com/live.mp4",
                },
            ]
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert len(result) == 2
        assert result[0].media_type == "image"
        assert result[1].media_type == "video"

    def test_pics_array_with_gifvideos(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pics": [
                {
                    "large": {"url": "https://img.com/g.jpg"},
                    "type": "gifvideos",
                    "videoSrc": "https://video.com/gif.mp4",
                },
            ]
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert len(result) == 2

    def test_pic_infos_dict_pic_type_with_original(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pic_num": 1,
            "pic_infos": {
                "abc": {
                    "type": "pic",
                    "original": {"url": "https://img.com/orig.jpg"},
                    "large": {"url": "https://img.com/large.jpg"},
                }
            },
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://img.com/orig.jpg"

    def test_pic_infos_dict_pic_type_no_original(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pic_num": 1,
            "pic_infos": {
                "abc": {
                    "type": "pic",
                    "original": None,
                    "large": {"url": "https://img.com/large.jpg"},
                }
            },
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://img.com/large.jpg"

    def test_pic_infos_live_photo_with_original_and_mp4_video(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pic_num": 1,
            "pic_infos": {
                "abc": {
                    "type": "live_photo",
                    "original": {"url": "https://img.com/orig.jpg"},
                    "large": {"url": "https://img.com/large.jpg"},
                    "video": {"url": "https://video.com/live.mp4"},
                }
            },
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert len(result) == 2
        assert result[0].media_type == "image"
        assert result[1].media_type == "video"

    def test_pic_infos_live_photo_no_original(self):
        """When original is None, falls back to MediaFile(pic["large"]["url"]) which
        raises TypeError (source code bug: positional arg goes to media_type, missing url)."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pic_num": 1,
            "pic_infos": {
                "abc": {
                    "type": "livephoto",
                    "original": None,
                    "large": {"url": "https://img.com/large.jpg"},
                    "video": {"url": "https://video.com/live.mp4"},
                }
            },
        }
        with pytest.raises(TypeError):
            WeiboDataProcessor._get_pictures(weibo_info)

    def test_pic_infos_live_photo_non_mp4_extension_skipped(self):
        """Live photo video with non-mp4 extension (e.g. .jpg) is skipped."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pic_num": 1,
            "pic_infos": {
                "abc": {
                    "type": "live_photo",
                    "original": {"url": "https://img.com/orig.jpg"},
                    "large": {"url": "https://img.com/large.jpg"},
                    "video": {"url": "https://video.com/file.jpg"},
                }
            },
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        # Should have the image but NOT the video since extension is .jpg not .mp4
        assert len(result) == 1
        assert result[0].media_type == "image"

    def test_pic_infos_gif_type(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pic_num": 1,
            "pic_infos": {
                "abc": {
                    "type": "gif",
                    "video": "https://video.com/gif.mp4",
                }
            },
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert len(result) == 1
        assert result[0].media_type == "video"

    def test_pic_infos_empty_dict(self):
        """pic_infos is present but empty dict."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "pic_num": 1,
            "pic_infos": {},
        }
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert result == []

    def test_pics_array_empty(self):
        """pics key exists but is an empty list."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {"pics": []}
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert result == []

    def test_pics_none(self):
        """pics key is None (falsy)."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {"pics": None}
        # None is falsy so goes to elif branch
        result = WeiboDataProcessor._get_pictures(weibo_info)
        assert result == []


# ---------------------------------------------------------------------------
# _get_videos (static)
# ---------------------------------------------------------------------------

class TestGetVideos:
    def test_no_page_info(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        result = WeiboDataProcessor._get_videos({})
        assert result == []

    def test_video_from_urls(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "page_info": {
                "type": "video",
                "urls": {"mp4_720p_mp4": "https://video.com/720p.mp4"},
            }
        }
        result = WeiboDataProcessor._get_videos(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://video.com/720p.mp4"

    def test_video_from_media_info_fallback(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "page_info": {
                "type": "video",
                "media_info": {"mp4_sd_url": "https://video.com/sd.mp4"},
            }
        }
        result = WeiboDataProcessor._get_videos(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://video.com/sd.mp4"

    def test_video_object_type(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "page_info": {
                "object_type": "video",
                "urls": {"stream_url": "https://video.com/stream.mp4"},
            }
        }
        result = WeiboDataProcessor._get_videos(weibo_info)
        assert len(result) == 1

    def test_non_video_type_skipped(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "page_info": {
                "type": "article",
                "urls": {"mp4_720p_mp4": "https://video.com/720p.mp4"},
            }
        }
        result = WeiboDataProcessor._get_videos(weibo_info)
        assert result == []

    def test_page_info_no_urls_or_media_info(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {"page_info": {"type": "video"}}
        result = WeiboDataProcessor._get_videos(weibo_info)
        assert result == []

    def test_video_key_fallback_order(self):
        """Falls through keys until finding one with a value."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "page_info": {
                "type": "video",
                "urls": {
                    "mp4_720p_mp4": None,
                    "mp4_hd_url": None,
                    "hevc_mp4_hd": "https://video.com/hevc.mp4",
                },
            }
        }
        result = WeiboDataProcessor._get_videos(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://video.com/hevc.mp4"

    def test_video_no_matching_key(self):
        """None of the known keys match, video_url stays None."""
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "page_info": {
                "type": "video",
                "urls": {"unknown_key": "https://video.com/x.mp4"},
            }
        }
        result = WeiboDataProcessor._get_videos(weibo_info)
        assert len(result) == 1
        assert result[0].url is None


# ---------------------------------------------------------------------------
# _get_mix_media (static)
# ---------------------------------------------------------------------------

class TestGetMixMedia:
    def test_no_mix_media(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        result = WeiboDataProcessor._get_mix_media({})
        assert result == []

    def test_pic_type_with_original(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "mix_media_info": {
                "items": [
                    {
                        "type": "pic",
                        "data": {
                            "original": {"url": "https://img.com/orig.jpg"},
                            "large": {"url": "https://img.com/large.jpg"},
                        },
                    }
                ]
            }
        }
        result = WeiboDataProcessor._get_mix_media(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://img.com/orig.jpg"

    def test_pic_type_no_original(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "mix_media_info": {
                "items": [
                    {
                        "type": "pic",
                        "data": {
                            "original": None,
                            "large": {"url": "https://img.com/large.jpg"},
                        },
                    }
                ]
            }
        }
        result = WeiboDataProcessor._get_mix_media(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://img.com/large.jpg"

    def test_live_photo_with_original(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "mix_media_info": {
                "items": [
                    {
                        "type": "live_photo",
                        "data": {
                            "original": {"url": "https://img.com/orig.jpg"},
                            "large": {"url": "https://img.com/large.jpg"},
                            "video": {"url": "https://video.com/live.mp4"},
                        },
                    }
                ]
            }
        }
        result = WeiboDataProcessor._get_mix_media(weibo_info)
        assert len(result) == 2
        assert result[0].media_type == "image"
        assert result[1].media_type == "video"

    def test_live_photo_no_original(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "mix_media_info": {
                "items": [
                    {
                        "type": "livephoto",
                        "data": {
                            "original": None,
                            "large": {"url": "https://img.com/large.jpg"},
                            "video": {"url": "https://video.com/live.mp4"},
                        },
                    }
                ]
            }
        }
        result = WeiboDataProcessor._get_mix_media(weibo_info)
        assert len(result) == 2
        assert result[0].url == "https://img.com/large.jpg"

    def test_gif_type(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "mix_media_info": {
                "items": [
                    {
                        "type": "gif",
                        "data": {"video": {"url": "https://video.com/gif.mp4"}},
                    }
                ]
            }
        }
        result = WeiboDataProcessor._get_mix_media(weibo_info)
        assert len(result) == 1
        assert result[0].media_type == "video"

    def test_video_type(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "mix_media_info": {
                "items": [
                    {
                        "type": "video",
                        "stream_url_hd": None,
                        "data": {
                            "media_info": {
                                "mp4_720p_mp4": "https://video.com/720p.mp4",
                            }
                        },
                    }
                ]
            }
        }
        result = WeiboDataProcessor._get_mix_media(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://video.com/720p.mp4"

    def test_video_type_fallback_keys(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        weibo_info = {
            "mix_media_info": {
                "items": [
                    {
                        "type": "video",
                        "data": {
                            "media_info": {
                                "stream_url": "https://video.com/stream.mp4",
                            }
                        },
                    }
                ]
            }
        }
        result = WeiboDataProcessor._get_mix_media(weibo_info)
        assert len(result) == 1
        assert result[0].url == "https://video.com/stream.mp4"


# ---------------------------------------------------------------------------
# _parse_weibo_info (static)
# ---------------------------------------------------------------------------

class TestParseWeiboInfo:
    def test_jmespath_extraction(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
        data = {
            "id": "4900001",
            "user": {
                "screen_name": "TestUser",
                "profile_url": "https://weibo.com/u/123",
                "id": 123,
            },
            "created_at": "Mon Jan 01",
            "source": "iPhone",
            "region_name": "Beijing",
            "text": "<p>Hello</p>",
            "text_raw": "Hello",
            "textLength": 5,
            "isLongText": False,
            "pic_num": 0,
            "pic_video": None,
            "pic_infos": None,
            "page_info": None,
            "pics": None,
            "mix_media_info": None,
            "url_struct": None,
            "attitudes_count": 100,
            "comments_count": 50,
            "reposts_count": 20,
            "retweeted_status": None,
        }
        result = WeiboDataProcessor._parse_weibo_info(data)
        assert result["id"] == "4900001"
        assert result["author"] == "TestUser"
        assert result["is_long_text"] is False
        assert result["attitudes_count"] == 100


# ---------------------------------------------------------------------------
# _get_weibo_info routing
# ---------------------------------------------------------------------------

class TestGetWeiboInfo:
    @pytest.mark.asyncio
    async def test_webpage_method(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")
        with patch.object(wp, "_get_weibo_info_webpage", new_callable=AsyncMock, return_value={"id": "123", "user": {"screen_name": "u", "profile_url": "p", "id": 1}, "isLongText": False}):
            result = await wp._get_weibo_info(method="webpage")
        assert result["id"] == "123"

    @pytest.mark.asyncio
    async def test_api_method(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")
        with patch.object(wp, "_get_weibo_info_api", new_callable=AsyncMock, return_value={"id": "123", "user": {"screen_name": "u", "profile_url": "p", "id": 1}, "isLongText": False}):
            result = await wp._get_weibo_info(method="api")
        assert result["id"] == "123"

    @pytest.mark.asyncio
    async def test_invalid_method_raises(self):
        """Invalid method raises ValueError, which propagates (not wrapped in ConnectionError
        because ConnectionError except only catches ConnectionError)."""
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")
        with pytest.raises(ValueError, match="method must be webpage or api"):
            await wp._get_weibo_info(method="invalid")

    @pytest.mark.asyncio
    async def test_default_method_from_init(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123", method="webpage")
        with patch.object(wp, "_get_weibo_info_webpage", new_callable=AsyncMock, return_value={"id": "123", "user": {"screen_name": "u", "profile_url": "p", "id": 1}, "isLongText": False}):
            result = await wp._get_weibo_info(method=None)
        assert result is not None

    @pytest.mark.asyncio
    async def test_connection_error_propagated(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")
        with patch.object(wp, "_get_weibo_info_api", new_callable=AsyncMock, side_effect=ConnectionError("net fail")):
            with pytest.raises(ConnectionError, match="network issues"):
                await wp._get_weibo_info(method="api")


# ---------------------------------------------------------------------------
# _get_weibo_info_webpage
# ---------------------------------------------------------------------------

class TestGetWeiboInfoWebpage:
    @pytest.mark.asyncio
    async def test_successful_parse(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        # Build HTML that matches the real Weibo page structure.
        # The status JSON is inside a JS array: [{...}], so after all parsing
        # steps, we get valid JSON. Key: extra `}]` after the status object.
        html_body = 'prefix "status":{"id":"123","text":"hello"}}],"hotScheme":"x"'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_body

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.httpx.AsyncClient", return_value=mock_client):
            result = await wp._get_weibo_info_webpage()
        assert result.get("id") == "123"

    @pytest.mark.asyncio
    async def test_redirect_302(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        redirect_resp = MagicMock()
        redirect_resp.status_code = 302
        redirect_resp.headers = {"Location": "https://m.weibo.cn/detail/123?new=1"}

        final_resp = MagicMock()
        final_resp.status_code = 200
        final_resp.text = '"status":{"id":"123"}}],"hotScheme":"x"'

        mock_client = AsyncMock()
        mock_client.get.side_effect = [redirect_resp, final_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.httpx.AsyncClient", return_value=mock_client):
            result = await wp._get_weibo_info_webpage()
        assert result.get("id") == "123"

    @pytest.mark.asyncio
    async def test_json_parse_failure(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '"status":NOT_VALID_JSON,"hotScheme":"x"'

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.httpx.AsyncClient", return_value=mock_client):
            result = await wp._get_weibo_info_webpage()
        assert result == {}


# ---------------------------------------------------------------------------
# _get_weibo_info_api
# ---------------------------------------------------------------------------

class TestGetWeiboInfoApi:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": 1, "id": "123"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.httpx.AsyncClient", return_value=mock_client):
            result = await wp._get_weibo_info_api()
        assert result["ok"] == 1

    @pytest.mark.asyncio
    async def test_ok_zero_raises(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": 0}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ConnectionError):
                await wp._get_weibo_info_api()

    @pytest.mark.asyncio
    async def test_empty_response_raises(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ConnectionError):
                await wp._get_weibo_info_api()

    @pytest.mark.asyncio
    async def test_http_error_raises(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 error")

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ConnectionError):
                await wp._get_weibo_info_api()


# ---------------------------------------------------------------------------
# _get_long_weibo_info_api
# ---------------------------------------------------------------------------

class TestGetLongWeiboInfoApi:
    @pytest.mark.asyncio
    async def test_calls_get_response_json(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.get_response_json", new_callable=AsyncMock, return_value={"data": {"longTextContent": "full text"}}) as mock_fn:
            result = await wp._get_long_weibo_info_api()
        assert result["data"]["longTextContent"] == "full text"
        mock_fn.assert_called_once()


# ---------------------------------------------------------------------------
# _get_weibo (fallback logic)
# ---------------------------------------------------------------------------

class TestGetWeibo:
    @pytest.mark.asyncio
    async def test_api_succeeds(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = {
            "id": "123",
            "author": "user",
            "author_url": "https://weibo.com/u/1",
            "user_id": 1,
            "created": "2024",
            "source": "iPhone",
            "region_name": "BJ",
            "text": "<p>Hello</p>",
            "is_long_text": False,
            "attitudes_count": 0,
            "comments_count": 0,
            "reposts_count": 0,
            "pic_num": 0,
            "pic_infos": None,
            "page_info": None,
            "pics": None,
            "mix_media_info": None,
            "retweeted_status": None,
            "pic_video": None,
        }
        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock, return_value=weibo_info):
            with patch.object(wp, "_process_weibo_item", new_callable=AsyncMock):
                await wp._get_weibo()

    @pytest.mark.asyncio
    async def test_api_fails_webpage_succeeds(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = {"id": "123", "author": "u"}
        call_count = 0

        async def side_effect(method=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("api fail")
            return weibo_info

        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock, side_effect=side_effect):
            with patch.object(wp, "_process_weibo_item", new_callable=AsyncMock):
                await wp._get_weibo()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_both_fail_raises(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock, side_effect=ConnectionError("fail")):
            with pytest.raises(ConnectionError):
                await wp._get_weibo()

    @pytest.mark.asyncio
    async def test_process_item_exception_caught(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock, return_value={"id": "123"}):
            with patch.object(wp, "_process_weibo_item", new_callable=AsyncMock, side_effect=Exception("process fail")):
                # Should not raise, exception is caught and logged
                await wp._get_weibo()


# ---------------------------------------------------------------------------
# _process_weibo_item
# ---------------------------------------------------------------------------

class TestProcessWeiboItem:
    def _make_weibo_info(self, **overrides):
        info = {
            "id": "123",
            "author": "TestUser",
            "author_url": "https://weibo.com/u/1",
            "user_id": 1,
            "created": "2024-01-01",
            "source": "iPhone",
            "region_name": "Beijing",
            "text": "<p>Hello world</p>",
            "is_long_text": False,
            "attitudes_count": 10,
            "comments_count": 5,
            "reposts_count": 3,
            "pic_num": 0,
            "pic_infos": None,
            "page_info": None,
            "pics": None,
            "mix_media_info": None,
            "retweeted_status": None,
            "pic_video": None,
        }
        info.update(overrides)
        return info

    @pytest.mark.asyncio
    async def test_short_text(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info()
        await wp._process_weibo_item(weibo_info)
        assert wp._data["category"] == "weibo"
        assert wp._data["title"] == "TestUser的微博"
        assert wp._data["message_type"] == MessageType.SHORT

    @pytest.mark.asyncio
    async def test_long_text_truncated_webpage_fallback(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info(
            is_long_text=True,
            text='<p>Short text</p><span class="expand">展开</span>',
        )
        longtext_info = {"text": "<p>Full long text here</p>", "is_long_text": True}
        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock, return_value=longtext_info):
            await wp._process_weibo_item(weibo_info)
        assert "Full long text here" in wp._data.get("raw_content", "")

    @pytest.mark.asyncio
    async def test_long_text_webpage_returns_none_falls_to_api(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info(
            is_long_text=True,
            text="<p>Truncated</p>展开",
        )
        longtext_webpage_info = {"text": None}  # fails
        longtext_api_info = {"data": {"longTextContent": "<p>API full text</p>"}}

        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock, return_value=longtext_webpage_info):
            with patch.object(wp, "_get_long_weibo_info_api", new_callable=AsyncMock, return_value=longtext_api_info):
                await wp._process_weibo_item(weibo_info)
        assert "API full text" in wp._data.get("raw_content", "")

    @pytest.mark.asyncio
    async def test_long_text_both_fallbacks_fail(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info(
            is_long_text=True,
            text="",  # empty text, is_long_text=True
        )

        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock, side_effect=Exception("webpage fail")):
            with patch.object(wp, "_get_long_weibo_info_api", new_callable=AsyncMock, side_effect=Exception("api fail")):
                # Should not raise, just logs errors and continues with empty/original text
                await wp._process_weibo_item(weibo_info)

    @pytest.mark.asyncio
    async def test_long_text_not_truncated_skips_refetch(self):
        """is_long_text=True but text is not truncated (has real content), skips re-fetch."""
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info(
            is_long_text=True,
            text="<p>Already complete long text</p>",
        )
        # _get_weibo_info should NOT be called for re-fetch
        with patch.object(wp, "_get_weibo_info", new_callable=AsyncMock) as mock_info:
            await wp._process_weibo_item(weibo_info)
            mock_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_retweeted_status(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        retweeted = {"id": "456", "mid": None, "idstr": None}
        weibo_info = self._make_weibo_info(retweeted_status=retweeted)

        retweeted_result = {
            "text": " retweeted text",
            "content": "<p>retweeted content</p>",
            "media_files": [],
        }

        # _process_weibo_item calls WeiboDataProcessor(url=...) then .get_item() on that instance.
        # WeiboDataProcessor is referenced by name in the module for both the constructor call AND
        # static methods like _weibo_html_text_clean. We use a wrapper class that preserves statics.
        original_new = WeiboDataProcessor.__new__
        original_init = WeiboDataProcessor.__init__

        class MockWDP(WeiboDataProcessor):
            """Subclass that overrides get_item to return mock data."""
            async def get_item(self):
                return retweeted_result

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.WeiboDataProcessor", MockWDP):
            await wp._process_weibo_item(weibo_info)
        assert "retweeted text" in wp._data.get("text", "")

    @pytest.mark.asyncio
    async def test_retweeted_status_mid_fallback(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        retweeted = {"id": None, "mid": "789", "idstr": None}
        weibo_info = self._make_weibo_info(retweeted_status=retweeted)

        retweeted_result = {
            "text": " rt text",
            "content": "<p>rt</p>",
            "media_files": [],
        }

        class MockWDP(WeiboDataProcessor):
            async def get_item(self):
                return retweeted_result

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.WeiboDataProcessor", MockWDP):
            await wp._process_weibo_item(weibo_info)

    @pytest.mark.asyncio
    async def test_retweeted_status_idstr_fallback(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        retweeted = {"id": None, "mid": None, "idstr": "101112"}
        weibo_info = self._make_weibo_info(retweeted_status=retweeted)

        retweeted_result = {
            "text": " rt text",
            "content": "<p>rt</p>",
            "media_files": [],
        }

        class MockWDP(WeiboDataProcessor):
            async def get_item(self):
                return retweeted_result

        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.WeiboDataProcessor", MockWDP):
            await wp._process_weibo_item(weibo_info)

    @pytest.mark.asyncio
    async def test_with_video_media(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info(
            page_info={
                "type": "video",
                "urls": {"mp4_720p_mp4": "https://video.com/v.mp4"},
            },
        )
        await wp._process_weibo_item(weibo_info)
        has_video = any(
            mf["media_type"] == "video"
            for mf in wp._data.get("media_files", [])
        )
        assert has_video

    @pytest.mark.asyncio
    async def test_with_image_media_in_text(self):
        """Images from _weibo_html_text_clean (fw_pics) become media_files."""
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info(
            text='<p>text</p><a href="https://img.com/big.jpg">查看图片</a>',
        )
        await wp._process_weibo_item(weibo_info)
        has_image = any(
            mf["media_type"] == "image"
            for mf in wp._data.get("media_files", [])
        )
        assert has_image

    @pytest.mark.asyncio
    async def test_long_text_message_type(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>" + "A" * 800 + "</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info(text="<p>" + "A" * 800 + "</p>")
        await wp._process_weibo_item(weibo_info)
        assert wp._data["message_type"] == MessageType.LONG

    @pytest.mark.asyncio
    async def test_text_ending_with_newline_stripped(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "text\n"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = self._make_weibo_info()
        await wp._process_weibo_item(weibo_info)
        assert not wp._data["text"].endswith("\n")

    @pytest.mark.asyncio
    async def test_text_not_ending_with_newline(self):
        """When rendered text doesn't end with newline, it is kept as-is."""
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.short_text_template") as mock_short:
            mock_short.render.return_value = "text without newline"
            with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.content_template") as mock_content:
                mock_content.render.return_value = "<p>content</p>"
                with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
                    mock_template = MagicMock()
                    mock_template.render.return_value = "<p>rendered</p>"
                    mock_env.get_template.return_value = mock_template
                    from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
                    wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

                weibo_info = self._make_weibo_info()
                await wp._process_weibo_item(weibo_info)
                assert wp._data["text"] == "text without newline"


# ---------------------------------------------------------------------------
# get_item / process_data
# ---------------------------------------------------------------------------

class TestGetItemAndProcessData:
    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        wp._data = {
            "url": "https://m.weibo.cn/detail/123",
            "telegraph_url": "",
            "content": "<p>c</p>",
            "text": "t",
            "media_files": [],
            "author": "a",
            "title": "ti",
            "author_url": "au",
            "category": "weibo",
            "message_type": MessageType.SHORT,
            "id": "123",
        }
        with patch.object(wp, "_get_weibo", new_callable=AsyncMock):
            result = await wp.get_item()
        assert isinstance(result, dict)
        assert result["id"] == "123"

    @pytest.mark.asyncio
    async def test_process_data_calls_get_weibo(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        with patch.object(wp, "_get_weibo", new_callable=AsyncMock) as mock_get:
            await wp.process_data()
            mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# WeiboScraper
# ---------------------------------------------------------------------------

class TestWeiboScraper:
    @pytest.mark.asyncio
    async def test_get_processor_by_url(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboScraper, WeiboDataProcessor
            ws = WeiboScraper()
            processor = await ws.get_processor_by_url("https://m.weibo.cn/detail/456")
        assert isinstance(processor, WeiboDataProcessor)
        assert processor.id == "456"

    def test_weibo_cookies_class_attr(self):
        from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboScraper
        # Should have weibo_cookies attribute (may be None in test env)
        assert hasattr(WeiboScraper, "weibo_cookies")


# ---------------------------------------------------------------------------
# _get_media_files
# ---------------------------------------------------------------------------

class TestGetMediaFiles:
    def test_aggregates_all_sources(self):
        with patch("fastfetchbot_shared.services.scrapers.weibo.scraper.JINJA2_ENV") as mock_env:
            mock_template = MagicMock()
            mock_template.render.return_value = "<p>rendered</p>"
            mock_env.get_template.return_value = mock_template
            from fastfetchbot_shared.services.scrapers.weibo.scraper import WeiboDataProcessor
            wp = WeiboDataProcessor(url="https://m.weibo.cn/detail/123")

        weibo_info = {
            "pics": [{"large": {"url": "https://img.com/1.jpg"}, "type": "normal"}],
            "pic_num": 0,
            "pic_infos": None,
            "page_info": {
                "type": "video",
                "urls": {"mp4_720p_mp4": "https://video.com/v.mp4"},
            },
            "mix_media_info": None,
        }
        result = wp._get_media_files(weibo_info)
        assert len(result) == 2  # 1 image + 1 video

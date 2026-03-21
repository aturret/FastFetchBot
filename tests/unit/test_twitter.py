"""
Unit tests for the Twitter scraper module.

Covers:
- packages/shared/fastfetchbot_shared/services/scrapers/twitter/__init__.py
- packages/shared/fastfetchbot_shared/services/scrapers/twitter/config.py

Every code path is exercised: __init__, get_item, get_twitter,
_get_response_tweet_data (iteration + fallback), _rapidapi_get_response_tweet_data
(success, error dict, error string, non-200), _api_client_get_response_tweet_data,
_process_tweet routing, _process_tweet_twitter135 (all entry types + TweetWithVisibilityResults),
process_single_tweet_Twitter135, parse_single_tweet_Twitter135,
parse_tweet_data_Twitter135, _process_tweet_Twitter154, parse_article_content,
_get_request_headers, _find_article_media_url, _apply_inline_formatting.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Dict

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _minimal_twitter135_response(
    tid="123456",
    name="TestUser",
    username="testuser",
    text="Hello world",
    full_text=None,
    media=None,
    quoted_tweet=None,
    article=None,
    extra_entries=None,
    tweet_typename="Tweet",
):
    """Build a minimal Twitter135-shaped API response dict."""
    tweet_result = {
        "__typename": tweet_typename,
        "rest_id": tid,
        "core": {
            "user_results": {
                "result": {
                    "legacy": {"name": name, "screen_name": username},
                }
            }
        },
        "legacy": {
            "created_at": "Mon Jan 01 00:00:00 +0000 2024",
            "full_text": text,
            "extended_entities": {"media": media} if media else {},
        },
        "quoted_status_result": {"result": quoted_tweet} if quoted_tweet else {},
    }
    if full_text:
        tweet_result["note_tweet"] = {
            "note_tweet_results": {"result": {"text": full_text}}
        }
    if article:
        tweet_result["article"] = {"article_results": {"result": article}}

    if tweet_typename == "TweetWithVisibilityResults":
        tweet_result_wrapper = {
            "__typename": "TweetWithVisibilityResults",
            "tweet": {
                "__typename": "Tweet",
                "rest_id": tid,
                "core": tweet_result["core"],
                "legacy": tweet_result["legacy"],
                "quoted_status_result": tweet_result.get("quoted_status_result", {}),
            },
        }
        if full_text:
            tweet_result_wrapper["tweet"]["note_tweet"] = tweet_result["note_tweet"]
        if article:
            tweet_result_wrapper["tweet"]["article"] = tweet_result["article"]
        tweet_result = tweet_result_wrapper

    main_entry = {
        "content": {
            "entryType": "TimelineTimelineItem",
            "itemContent": {
                "itemType": "TimelineTweet",
                "tweet_results": {"result": tweet_result},
            },
        }
    }
    entries = [main_entry]
    if extra_entries:
        entries.extend(extra_entries)

    return {
        "data": {
            "threaded_conversation_with_injections_v2": {
                "instructions": [
                    {"entries": entries},
                ]
            }
        }
    }


# ---------------------------------------------------------------------------
# config.py tests
# ---------------------------------------------------------------------------

class TestTwitterConfig:
    def test_all_scraper_list(self):
        from fastfetchbot_shared.services.scrapers.twitter.config import ALL_SCRAPER
        assert isinstance(ALL_SCRAPER, list)
        assert len(ALL_SCRAPER) > 0

    def test_all_single_scraper_list(self):
        from fastfetchbot_shared.services.scrapers.twitter.config import ALL_SINGLE_SCRAPER
        assert isinstance(ALL_SINGLE_SCRAPER, list)
        assert len(ALL_SINGLE_SCRAPER) > 0

    def test_scraper_info_keys(self):
        from fastfetchbot_shared.services.scrapers.twitter.config import SCRAPER_INFO
        for name, info in SCRAPER_INFO.items():
            assert "host" in info
            assert "top_domain" in info
            assert "params" in info

    def test_x_rapidapi_host(self):
        from fastfetchbot_shared.services.scrapers.twitter.config import X_RAPIDAPI_HOST
        assert X_RAPIDAPI_HOST == ".p.rapidapi.com"

    def test_short_limit(self):
        from fastfetchbot_shared.services.scrapers.twitter.config import SHORT_LIMIT
        assert SHORT_LIMIT == 600


# ---------------------------------------------------------------------------
# Twitter.__init__
# ---------------------------------------------------------------------------

class TestTwitterInit:
    def test_basic_init(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/12345")
        assert tw.tid == "12345"
        assert tw.url == "https://twitter.com/user/status/12345"
        assert tw.title == ""
        assert tw.author == ""
        assert tw.category == "twitter"
        assert tw.message_type == MessageType.SHORT
        assert tw.instruction == "threads"
        assert tw.scraper == "Twitter135"
        assert tw.include_comments is False
        assert tw.article_tweet is False

    def test_init_with_kwargs(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(
            url="https://x.com/user/status/999",
            scraper="Twitter154",
            instruction="single",
            include_comments=True,
        )
        assert tw.tid == "999"
        assert tw.scraper == "Twitter154"
        assert tw.instruction == "single"
        assert tw.include_comments is True


# ---------------------------------------------------------------------------
# get_item / get_twitter
# ---------------------------------------------------------------------------

class TestGetItem:
    @pytest.mark.asyncio
    async def test_get_item_returns_dict(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        resp = _minimal_twitter135_response()
        with patch.object(tw, "_get_response_tweet_data", new_callable=AsyncMock, return_value=resp):
            result = await tw.get_item()
        assert isinstance(result, dict)
        assert result["category"] == "twitter"

    @pytest.mark.asyncio
    async def test_get_twitter_calls_process(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        resp = _minimal_twitter135_response()
        with patch.object(tw, "_get_response_tweet_data", new_callable=AsyncMock, return_value=resp):
            with patch.object(tw, "_process_tweet") as mock_process:
                await tw.get_twitter()
                mock_process.assert_called_once_with(resp)


# ---------------------------------------------------------------------------
# _get_response_tweet_data
# ---------------------------------------------------------------------------

class TestGetResponseTweetData:
    @pytest.mark.asyncio
    async def test_threads_instruction_uses_all_scraper(self):
        """instruction == 'threads' iterates ALL_SCRAPER."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1", instruction="threads")
        with patch.object(tw, "_rapidapi_get_response_tweet_data", new_callable=AsyncMock, return_value={"ok": True}):
            # ALL_SCRAPER starts with "api-client" which triggers _api_client branch
            # but since it starts with "api-client" (not "Twitter"), it falls into elif
            with patch.object(tw, "_api_client_get_response_tweet_data", new_callable=AsyncMock, return_value={"ok": True}):
                result = await tw._get_response_tweet_data()
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_single_instruction_uses_all_single_scraper(self):
        """instruction != 'threads' uses ALL_SINGLE_SCRAPER."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1", instruction="single")
        with patch.object(tw, "_rapidapi_get_response_tweet_data", new_callable=AsyncMock, return_value={"data": 1}):
            result = await tw._get_response_tweet_data()
        # ALL_SINGLE_SCRAPER starts with Twitter154
        assert result == {"data": 1}
        assert tw.scraper == "Twitter154"

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When first scraper fails, tries next."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1", instruction="single")
        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("fail first")
            return {"ok": True}

        with patch.object(tw, "_rapidapi_get_response_tweet_data", new_callable=AsyncMock, side_effect=side_effect):
            result = await tw._get_response_tweet_data()
        assert result == {"ok": True}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_scrapers_fail_raises(self):
        """When all scrapers fail, raises exception."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1", instruction="single")
        with patch.object(tw, "_rapidapi_get_response_tweet_data", new_callable=AsyncMock, side_effect=Exception("fail")):
            with patch.object(tw, "_api_client_get_response_tweet_data", new_callable=AsyncMock, side_effect=Exception("fail")):
                with pytest.raises(Exception, match="No valid response from all Twitter scrapers"):
                    await tw._get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_api_client_scraper_path(self):
        """api-client scraper triggers _api_client_get_response_tweet_data."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1", instruction="threads")
        # ALL_SCRAPER = ["api-client", "Twitter135"] — first is api-client
        with patch.object(tw, "_api_client_get_response_tweet_data", new_callable=AsyncMock, return_value={"api": True}):
            result = await tw._get_response_tweet_data()
        assert result == {"api": True}


# ---------------------------------------------------------------------------
# _rapidapi_get_response_tweet_data
# ---------------------------------------------------------------------------

class TestRapidapiGetResponseTweetData:
    @pytest.mark.asyncio
    async def test_success_200(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": "valid"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.twitter.httpx.AsyncClient", return_value=mock_client):
            result = await tw._rapidapi_get_response_tweet_data()
        assert result == {"data": "valid"}

    @pytest.mark.asyncio
    async def test_error_dict_with_errors_key(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"errors": ["something"]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.twitter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Invalid response from Twitter API"):
                await tw._rapidapi_get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_error_dict_with_detail_key(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"detail": "rate limit"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.twitter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Invalid response from Twitter API"):
                await tw._rapidapi_get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_error_string_400(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = "400 Bad Request"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.twitter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Invalid response from Twitter API"):
                await tw._rapidapi_get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_error_string_429(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = "429 Too Many Requests"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.twitter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Invalid response from Twitter API"):
                await tw._rapidapi_get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_non_200_status(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.twitter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception, match="Invalid response from Twitter API"):
                await tw._rapidapi_get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_valid_list_response(self):
        """A list response (not dict/str) should be returned normally."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"data": "tweet"}]

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.services.scrapers.twitter.httpx.AsyncClient", return_value=mock_client):
            result = await tw._rapidapi_get_response_tweet_data()
        assert result == [{"data": "tweet"}]


# ---------------------------------------------------------------------------
# _api_client_get_response_tweet_data
# ---------------------------------------------------------------------------

class TestApiClientGetResponseTweetData:
    @pytest.mark.asyncio
    async def test_api_client(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123")
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.tweets_details.return_value = [{"data": "tweet_detail"}]

        with patch("fastfetchbot_shared.services.scrapers.twitter.Scraper", return_value=mock_scraper_instance):
            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=[{"data": "tweet_detail"}]):
                result = await tw._api_client_get_response_tweet_data()
        assert result == {"data": "tweet_detail"}


# ---------------------------------------------------------------------------
# _process_tweet routing
# ---------------------------------------------------------------------------

class TestProcessTweet:
    def test_routes_to_twitter135_for_api_client(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "api-client"
        with patch.object(tw, "_process_tweet_twitter135") as mock:
            tw._process_tweet({"data": 1})
            mock.assert_called_once_with({"data": 1})

    def test_routes_to_twitter135(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter135"
        with patch.object(tw, "_process_tweet_twitter135") as mock:
            tw._process_tweet({"data": 1})
            mock.assert_called_once_with({"data": 1})

    def test_routes_to_twitter154(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "Twitter154"
        with patch.object(tw, "_process_tweet_Twitter154") as mock:
            tw._process_tweet({"data": 1})
            mock.assert_called_once_with({"data": 1})

    def test_routes_to_twitter154_for_v24(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "twitter-v24"
        with patch.object(tw, "_process_tweet_Twitter154") as mock:
            tw._process_tweet({"data": 1})
            mock.assert_called_once_with({"data": 1})

    def test_unknown_scraper_does_nothing(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        tw.scraper = "unknown-scraper"
        # Should not raise
        tw._process_tweet({"data": 1})


# ---------------------------------------------------------------------------
# _process_tweet_twitter135
# ---------------------------------------------------------------------------

class TestProcessTweetTwitter135:
    def test_basic_tweet(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        resp = _minimal_twitter135_response(tid="123456", text="Hello")
        tw._process_tweet_twitter135(resp)
        assert tw.author == "TestUser"
        assert tw.title == "TestUser's Tweet"
        assert "Hello" in tw.text
        assert tw.message_type == MessageType.SHORT

    def test_long_tweet_sets_long_message_type(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        long_text = "A" * 700
        resp = _minimal_twitter135_response(tid="123456", text=long_text)
        tw._process_tweet_twitter135(resp)
        assert tw.message_type == MessageType.LONG

    def test_tweet_with_visibility_results(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        resp = _minimal_twitter135_response(
            tid="123456", text="Visible tweet", tweet_typename="TweetWithVisibilityResults"
        )
        tw._process_tweet_twitter135(resp)
        assert "Visible tweet" in tw.text

    def test_timeline_module_with_comments(self):
        """TimelineTimelineModule entries are processed when include_comments=True."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456", include_comments=True)
        comment_tweet = {
            "__typename": "Tweet",
            "rest_id": "999",
            "core": {"user_results": {"result": {"legacy": {"name": "Commenter", "screen_name": "commenter"}}}},
            "legacy": {"created_at": "Mon Jan 01 00:00:00 +0000 2024", "full_text": "Nice tweet!"},
            "quoted_status_result": {},
        }
        module_entry = {
            "content": {
                "entryType": "TimelineTimelineModule",
                "items": [
                    {
                        "item": {
                            "itemContent": {
                                "itemType": "TimelineTweet",
                                "tweet_results": {"result": comment_tweet},
                            }
                        }
                    }
                ],
            }
        }
        resp = _minimal_twitter135_response(tid="123456", extra_entries=[module_entry])
        tw._process_tweet_twitter135(resp)
        assert "Nice tweet!" in tw.text

    def test_timeline_module_without_comments_ignored(self):
        """TimelineTimelineModule entries are skipped when include_comments=False."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456", include_comments=False)
        module_entry = {
            "content": {
                "entryType": "TimelineTimelineModule",
                "items": [],
            }
        }
        resp = _minimal_twitter135_response(tid="123456", extra_entries=[module_entry])
        tw._process_tweet_twitter135(resp)
        # Should not crash and only contain main tweet
        assert "Hello world" in tw.text

    def test_entry_with_no_result_skipped(self):
        """When tweet_results.result is None, entry is skipped."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        empty_entry = {
            "content": {
                "entryType": "TimelineTimelineItem",
                "itemContent": {
                    "itemType": "TimelineTweet",
                    "tweet_results": {"result": None},
                },
            }
        }
        resp = _minimal_twitter135_response(tid="123456", extra_entries=[empty_entry])
        tw._process_tweet_twitter135(resp)
        # Should not crash

    def test_entry_non_timeline_tweet_skipped(self):
        """Entries with itemType != TimelineTweet are skipped."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        cursor_entry = {
            "content": {
                "entryType": "TimelineTimelineItem",
                "itemContent": {
                    "itemType": "TimelineCursor",
                },
            }
        }
        resp = _minimal_twitter135_response(tid="123456", extra_entries=[cursor_entry])
        tw._process_tweet_twitter135(resp)

    def test_unknown_entry_type_skipped(self):
        """Unknown entryType is skipped."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        unknown_entry = {
            "content": {
                "entryType": "TimelineUnknown",
            }
        }
        resp = _minimal_twitter135_response(tid="123456", extra_entries=[unknown_entry])
        tw._process_tweet_twitter135(resp)

    def test_article_tweet_sets_title_and_long(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        article = {
            "title": "My Article Title",
            "content_state": {"blocks": [], "entityMap": []},
            "media_entities": [],
        }
        resp = _minimal_twitter135_response(tid="123456", article=article)
        tw._process_tweet_twitter135(resp)
        assert tw.title == "My Article Title"
        assert tw.article_tweet is True
        assert tw.message_type == MessageType.LONG

    def test_module_item_with_no_result_skipped(self):
        """Module items with no tweet_results.result are skipped."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456", include_comments=True)
        module_entry = {
            "content": {
                "entryType": "TimelineTimelineModule",
                "items": [
                    {
                        "item": {
                            "itemContent": {
                                "itemType": "TimelineTweet",
                                "tweet_results": {"result": None},
                            }
                        }
                    }
                ],
            }
        }
        resp = _minimal_twitter135_response(tid="123456", extra_entries=[module_entry])
        tw._process_tweet_twitter135(resp)

    def test_module_item_non_timeline_tweet_skipped(self):
        """Module items that are not TimelineTweet are skipped."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456", include_comments=True)
        module_entry = {
            "content": {
                "entryType": "TimelineTimelineModule",
                "items": [
                    {
                        "item": {
                            "itemContent": {
                                "itemType": "TimelineCursor",
                            }
                        }
                    }
                ],
            }
        }
        resp = _minimal_twitter135_response(tid="123456", extra_entries=[module_entry])
        tw._process_tweet_twitter135(resp)


# ---------------------------------------------------------------------------
# process_single_tweet_Twitter135
# ---------------------------------------------------------------------------

class TestProcessSingleTweetTwitter135:
    def test_matching_tid_sets_author(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        tweet = {
            "tid": "123456",
            "name": "Author",
            "username": "author",
            "date": "2024-01-01",
            "text": "test",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        tw.process_single_tweet_Twitter135(tweet)
        assert tw.author == "Author"
        assert tw.author_url == "https://twitter.com/author"
        assert tw.date == "2024-01-01"
        assert tw.title == "Author's Tweet"

    def test_non_matching_tid(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        tweet = {
            "tid": "999",
            "name": "Other",
            "username": "other",
            "date": "2024-01-01",
            "text": "test",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        tw.process_single_tweet_Twitter135(tweet)
        assert tw.author == ""  # not set since tid doesn't match

    def test_quoted_tweet_recursive(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        quoted = {
            "__typename": "Tweet",
            "rest_id": "555",
            "core": {"user_results": {"result": {"legacy": {"name": "Quoted", "screen_name": "quoted"}}}},
            "legacy": {"created_at": "Mon Jan 01 00:00:00 +0000 2024", "full_text": "Quoted text"},
            "quoted_status_result": {},
        }
        tweet = {
            "tid": "123456",
            "name": "Author",
            "username": "author",
            "date": "2024-01-01",
            "text": "My tweet",
            "full_text": None,
            "media": None,
            "quoted_tweet": quoted,
            "article": None,
        }
        tw.process_single_tweet_Twitter135(tweet)
        assert "Quoted text" in tw.text_group or "Quoted text" in tw.content_group

    def test_article_with_title(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        tweet = {
            "tid": "123456",
            "name": "Author",
            "username": "author",
            "date": "2024-01-01",
            "text": "text",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": {
                "title": "Great Article",
                "content_state": {"blocks": [], "entityMap": []},
                "media_entities": [],
            },
        }
        tw.process_single_tweet_Twitter135(tweet)
        assert tw.title == "Great Article"
        assert tw.article_tweet is True

    def test_article_without_title_uses_text(self):
        """Article exists but has no title, falls back to full_text / text."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        tweet = {
            "tid": "123456",
            "name": "Author",
            "username": "author",
            "date": "2024-01-01",
            "text": "fallback text",
            "full_text": "long fallback",
            "media": None,
            "quoted_tweet": None,
            "article": {
                "title": "",
                "content_state": {"blocks": [], "entityMap": []},
                "media_entities": [],
            },
        }
        tw.process_single_tweet_Twitter135(tweet)
        # Empty title string is falsy, so title stays as tweet name's tweet
        # Actually: empty string is falsy in the `if tweet["article"].get("title")` check
        assert tw.title == "Author's Tweet"

    def test_hr_removal_for_matching_tid(self):
        """The first <hr> is removed from content_group for matching tid."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/123456")
        tweet = {
            "tid": "123456",
            "name": "Author",
            "username": "author",
            "date": "2024-01-01",
            "text": "test",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        tw.process_single_tweet_Twitter135(tweet)
        # The initial <hr> should be removed
        assert not tw.content_group.startswith("<hr>")


# ---------------------------------------------------------------------------
# parse_single_tweet_Twitter135 (static)
# ---------------------------------------------------------------------------

class TestParseSingleTweetTwitter135:
    def test_plain_text(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "Hello world",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert "Hello world" in result["text_group"]
        assert "Hello world" in result["content_group"]
        assert result["media_files"] == []

    def test_full_text_preferred(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "Short",
            "full_text": "Full long text here",
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert "Full long text here" in result["text_group"]

    def test_retweeted_prefix(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "text",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet, retweeted=True)
        assert result["content_group"].startswith("<p>Quoted:</p>")

    def test_not_retweeted_prefix(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "text",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet, retweeted=False)
        assert result["content_group"].startswith("<hr>")

    def test_photo_media(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "pics",
            "full_text": None,
            "media": [{"type": "photo", "media_url_https": "https://pbs.twimg.com/img1"}],
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "image"
        assert "?name=orig" in result["media_files"][0].url

    def test_video_media(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "vid",
            "full_text": None,
            "media": [
                {
                    "type": "video",
                    "video_info": {
                        "variants": [
                            {"bitrate": 100, "url": "https://vid.com/low.mp4"},
                            {"bitrate": 2000, "url": "https://vid.com/high.mp4"},
                            {"url": "https://vid.com/playlist.m3u8"},  # no bitrate
                        ]
                    },
                }
            ],
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "video"
        assert "high.mp4" in result["media_files"][0].url

    def test_animated_gif_media(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "gif",
            "full_text": None,
            "media": [
                {
                    "type": "animated_gif",
                    "video_info": {
                        "variants": [{"bitrate": 0, "url": "https://vid.com/gif.mp4"}]
                    },
                }
            ],
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert len(result["media_files"]) == 1
        assert result["media_files"][0].media_type == "video"

    def test_article_with_content(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "text",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": {
                "title": "Article Title",
                "content_state": {
                    "blocks": [
                        {"type": "unstyled", "text": "paragraph", "inlineStyleRanges": [], "entityRanges": []}
                    ],
                    "entityMap": [],
                },
                "media_entities": [],
            },
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert "Article Title" in result["text_group"]
        assert "<p>paragraph</p>" in result["content_group"]

    def test_article_no_title_uses_full_text(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "fallback",
            "full_text": "long fallback text",
            "media": None,
            "quoted_tweet": None,
            "article": {
                "title": "",
                "content_state": {"blocks": [], "entityMap": []},
                "media_entities": [],
            },
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert "long fallback text" in result["text_group"]

    def test_article_no_title_no_full_text_uses_text(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "basic text",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": {
                "title": "",
                "content_state": {"blocks": [], "entityMap": []},
                "media_entities": [],
            },
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        assert "basic text" in result["text_group"]

    def test_newlines_replaced_with_br(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tweet = {
            "tid": "1",
            "name": "User",
            "username": "user",
            "text": "line1\nline2",
            "full_text": None,
            "media": None,
            "quoted_tweet": None,
            "article": None,
        }
        result = Twitter.parse_single_tweet_Twitter135(tweet)
        # newlines are replaced with <br> by the .replace("\n", "<br>") call
        assert "\n" not in result["content_group"]


# ---------------------------------------------------------------------------
# parse_tweet_data_Twitter135 (static)
# ---------------------------------------------------------------------------

class TestParseTweetDataTwitter135:
    def test_jmespath_extraction(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        data = {
            "rest_id": "42",
            "core": {
                "user_results": {
                    "result": {
                        "legacy": {"name": "TestName", "screen_name": "testscreen"},
                    }
                }
            },
            "legacy": {
                "created_at": "Mon Jan 01",
                "full_text": "Hello",
                "extended_entities": {"media": [{"type": "photo"}]},
            },
            "note_tweet": {"note_tweet_results": {"result": {"text": "Long note"}}},
            "quoted_status_result": {"result": {"rest_id": "99"}},
            "article": {"article_results": {"result": {"title": "Art"}}},
        }
        result = Twitter.parse_tweet_data_Twitter135(data)
        assert result["tid"] == "42"
        assert result["name"] == "TestName"
        assert result["username"] == "testscreen"
        assert result["date"] == "Mon Jan 01"
        assert result["full_text"] == "Long note"
        assert result["text"] == "Hello"
        assert result["media"] == [{"type": "photo"}]
        assert result["quoted_tweet"] == {"rest_id": "99"}
        assert result["article"] == {"title": "Art"}

    def test_jmespath_with_core_name(self):
        """core.user_results.result.core.name takes precedence over legacy.name."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        data = {
            "rest_id": "1",
            "core": {
                "user_results": {
                    "result": {
                        "core": {"name": "CoreName", "screen_name": "corescreen"},
                        "legacy": {"name": "LegacyName", "screen_name": "legacyscreen"},
                    }
                }
            },
            "legacy": {"created_at": "", "full_text": ""},
        }
        result = Twitter.parse_tweet_data_Twitter135(data)
        assert result["name"] == "CoreName"
        assert result["username"] == "corescreen"


# ---------------------------------------------------------------------------
# _process_tweet_Twitter154
# ---------------------------------------------------------------------------

class TestProcessTweetTwitter154:
    def test_is_noop(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/1")
        # Should not raise
        tw._process_tweet_Twitter154({"data": "anything"})


# ---------------------------------------------------------------------------
# parse_article_content (static)
# ---------------------------------------------------------------------------

class TestParseArticleContent:
    def test_empty_article(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        html, media = Twitter.parse_article_content({})
        assert html == ""
        assert media == []

    def test_unstyled_block(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        article = {
            "content_state": {
                "blocks": [
                    {"type": "unstyled", "text": "Hello", "inlineStyleRanges": [], "entityRanges": []}
                ],
                "entityMap": [],
            }
        }
        html, media = Twitter.parse_article_content(article)
        assert "<p>Hello</p>" in html

    def test_header_two_block(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        article = {
            "content_state": {
                "blocks": [
                    {"type": "header-two", "text": "Title", "inlineStyleRanges": [], "entityRanges": []}
                ],
                "entityMap": [],
            }
        }
        html, media = Twitter.parse_article_content(article)
        assert "<h2>Title</h2>" in html

    def test_atomic_block_with_media(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        article = {
            "content_state": {
                "blocks": [
                    {
                        "type": "atomic",
                        "text": "",
                        "inlineStyleRanges": [],
                        "entityRanges": [{"key": 0}],
                    }
                ],
                "entityMap": [
                    {
                        "key": 0,
                        "value": {
                            "type": "MEDIA",
                            "data": {
                                "mediaItems": [{"mediaId": "123"}]
                            },
                        },
                    }
                ],
            },
            "media_entities": [
                {
                    "media_id": 123,
                    "media_info": {"original_img_url": "https://img.com/photo.jpg"},
                }
            ],
        }
        html, media = Twitter.parse_article_content(article)
        assert "<img src='https://img.com/photo.jpg'/>" in html
        assert len(media) == 1
        assert media[0].url == "https://img.com/photo.jpg"

    def test_atomic_block_non_media_entity_skipped(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        article = {
            "content_state": {
                "blocks": [
                    {
                        "type": "atomic",
                        "text": "",
                        "inlineStyleRanges": [],
                        "entityRanges": [{"key": 0}],
                    }
                ],
                "entityMap": [
                    {"key": 0, "value": {"type": "LINK", "data": {"url": "https://example.com"}}},
                ],
            },
        }
        html, media = Twitter.parse_article_content(article)
        assert html == ""
        assert media == []

    def test_atomic_block_media_not_found(self):
        """Media entity references a mediaId not in media_entities."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        article = {
            "content_state": {
                "blocks": [
                    {
                        "type": "atomic",
                        "text": "",
                        "inlineStyleRanges": [],
                        "entityRanges": [{"key": 0}],
                    }
                ],
                "entityMap": [
                    {
                        "key": 0,
                        "value": {
                            "type": "MEDIA",
                            "data": {"mediaItems": [{"mediaId": "999"}]},
                        },
                    }
                ],
            },
            "media_entities": [],
        }
        html, media = Twitter.parse_article_content(article)
        assert media == []

    def test_atomic_entity_key_not_found(self):
        """entity_ranges references a key not in entity_lookup."""
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        article = {
            "content_state": {
                "blocks": [
                    {
                        "type": "atomic",
                        "text": "",
                        "inlineStyleRanges": [],
                        "entityRanges": [{"key": 99}],
                    }
                ],
                "entityMap": [],
            },
        }
        html, media = Twitter.parse_article_content(article)
        assert html == ""
        assert media == []


# ---------------------------------------------------------------------------
# _get_request_headers
# ---------------------------------------------------------------------------

class TestGetRequestHeaders:
    def test_sets_headers_and_params(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/42")
        tw.scraper = "Twitter135"
        tw._get_request_headers()
        assert tw.host == "https://twitter135.p.rapidapi.com/v2/TweetDetail/"
        assert "X-RapidAPI-Key" in tw.headers
        assert "X-RapidAPI-Host" in tw.headers
        assert tw.headers["X-RapidAPI-Host"] == "twitter135.p.rapidapi.com"
        assert tw.params == {"id": "42"}

    def test_twitter154_headers(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        tw = Twitter(url="https://twitter.com/user/status/55")
        tw.scraper = "Twitter154"
        tw._get_request_headers()
        assert tw.host == "https://twitter154.p.rapidapi.com/tweet/details/"
        assert tw.params == {"tweet_id": "55"}


# ---------------------------------------------------------------------------
# _find_article_media_url (module-level)
# ---------------------------------------------------------------------------

class TestFindArticleMediaUrl:
    def test_found(self):
        from fastfetchbot_shared.services.scrapers.twitter import _find_article_media_url
        article = {
            "media_entities": [
                {
                    "media_id": 123,
                    "media_info": {"original_img_url": "https://img.com/1.jpg"},
                }
            ]
        }
        assert _find_article_media_url(article, "123") == "https://img.com/1.jpg"

    def test_not_found(self):
        from fastfetchbot_shared.services.scrapers.twitter import _find_article_media_url
        article = {"media_entities": []}
        assert _find_article_media_url(article, "999") == ""

    def test_no_media_entities_key(self):
        from fastfetchbot_shared.services.scrapers.twitter import _find_article_media_url
        assert _find_article_media_url({}, "1") == ""

    def test_id_comparison_as_string(self):
        from fastfetchbot_shared.services.scrapers.twitter import _find_article_media_url
        article = {
            "media_entities": [
                {"media_id": 42, "media_info": {"original_img_url": "url42"}},
            ]
        }
        assert _find_article_media_url(article, "42") == "url42"


# ---------------------------------------------------------------------------
# _apply_inline_formatting (module-level)
# ---------------------------------------------------------------------------

class TestApplyInlineFormatting:
    def test_empty_text(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        assert _apply_inline_formatting("", [], [], {}) == ""

    def test_no_styles_no_entities(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        assert _apply_inline_formatting("plain text", [], [], {}) == "plain text"

    def test_bold(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "Hello",
            [{"offset": 0, "length": 5, "style": "Bold"}],
            [],
            {},
        )
        assert result == "<b>Hello</b>"

    def test_italic(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "Hello",
            [{"offset": 0, "length": 5, "style": "Italic"}],
            [],
            {},
        )
        assert result == "<i>Hello</i>"

    def test_link(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "click",
            [],
            [{"key": 0, "offset": 0, "length": 5}],
            {"0": {"type": "LINK", "data": {"url": "https://example.com"}}},
        )
        assert "<a href='https://example.com'>click</a>" in result

    def test_bold_and_italic_combined(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "AB",
            [
                {"offset": 0, "length": 1, "style": "Bold"},
                {"offset": 1, "length": 1, "style": "Italic"},
            ],
            [],
            {},
        )
        assert "<b>A</b>" in result
        assert "<i>B</i>" in result

    def test_bold_italic_same_range(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "AB",
            [
                {"offset": 0, "length": 2, "style": "Bold"},
                {"offset": 0, "length": 2, "style": "Italic"},
            ],
            [],
            {},
        )
        assert "<b>" in result
        assert "<i>" in result

    def test_link_with_non_link_entity_ignored(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "text",
            [],
            [{"key": 0, "offset": 0, "length": 4}],
            {"0": {"type": "MEDIA", "data": {}}},
        )
        assert result == "text"

    def test_entity_key_not_in_lookup(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "text",
            [],
            [{"key": 99, "offset": 0, "length": 4}],
            {},
        )
        assert result == "text"

    def test_style_range_exceeds_text_length(self):
        """Style range extends beyond text length (min(end, n) safety)."""
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "Hi",
            [{"offset": 0, "length": 100, "style": "Bold"}],
            [],
            {},
        )
        assert result == "<b>Hi</b>"

    def test_partial_bold(self):
        from fastfetchbot_shared.services.scrapers.twitter import _apply_inline_formatting
        result = _apply_inline_formatting(
            "Hello World",
            [{"offset": 0, "length": 5, "style": "Bold"}],
            [],
            {},
        )
        assert "<b>Hello</b>" in result
        assert " World" in result

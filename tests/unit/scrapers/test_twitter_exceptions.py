"""Tests for exception handling in Twitter scraper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.exceptions import ScraperError, ScraperParseError


class TestGetResponseTweetData:
    @pytest.mark.asyncio
    async def test_all_scrapers_fail_raises_scraper_error(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter

        tw = Twitter(url="https://twitter.com/user/status/123")

        with patch.object(
            tw, "_rapidapi_get_response_tweet_data",
            new_callable=AsyncMock,
            side_effect=ScraperParseError("API error"),
        ), patch.object(
            tw, "_api_client_get_response_tweet_data",
            new_callable=AsyncMock,
            side_effect=RuntimeError("client error"),
        ):
            with pytest.raises(ScraperError, match="No valid response from all Twitter scrapers"):
                await tw._get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_first_scraper_fails_falls_through(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter

        tw = Twitter(url="https://twitter.com/user/status/456")
        fake_data = {
            "data": {
                "threaded_conversation_with_injections_v2": {
                    "instructions": [{"entries": []}]
                }
            }
        }

        with patch.object(
            tw, "_rapidapi_get_response_tweet_data",
            new_callable=AsyncMock,
            side_effect=RuntimeError("first failed"),
        ), patch.object(
            tw, "_api_client_get_response_tweet_data",
            new_callable=AsyncMock,
            return_value=fake_data,
        ):
            # Should fall through to api-client and succeed
            result = await tw._get_response_tweet_data()
            assert result == fake_data


class TestRapidapiResponseValidation:
    @pytest.mark.asyncio
    async def test_error_response_raises_scraper_parse_error(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter
        import httpx

        tw = Twitter(url="https://twitter.com/user/status/789")
        tw.scraper = "Twitter135"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "rate limited"}]}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(tw, "_get_request_headers"):
                with pytest.raises(ScraperParseError, match="Invalid response"):
                    await tw._rapidapi_get_response_tweet_data()

    @pytest.mark.asyncio
    async def test_non_200_raises_scraper_parse_error(self):
        from fastfetchbot_shared.services.scrapers.twitter import Twitter

        tw = Twitter(url="https://twitter.com/user/status/000")
        tw.scraper = "Twitter135"

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(tw, "_get_request_headers"):
                with pytest.raises(ScraperParseError, match="Invalid response"):
                    await tw._rapidapi_get_response_tweet_data()

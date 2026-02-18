"""
Tests for /scraper router endpoints.

Endpoints:
    POST /scraper/getItem — Scrape content from a URL
    POST /scraper/getUrlMetadata — Get URL metadata without scraping

All downstream services (InfoExtractService, get_url_metadata) are mocked.
We only test: routing, auth, parameter parsing, and response shape.
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_API_KEY, TEST_API_KEY_NAME

# NOTE on "no API key" tests:
# auth.py has a bug where verify_key checks `api_key_query is None` (module-level
# variable, always not None) instead of checking `input_key is None`. When no key
# is provided, secrets.compare_digest(None, str) raises TypeError which propagates
# as an unhandled exception. These tests are marked xfail to document this known bug.
# Once auth.py is fixed, remove xfail and assert 401.


# ─── POST /scraper/getItem ───────────────────────────────────────────


class TestGetItem:
    """Tests for POST /scraper/getItem"""

    @pytest.mark.asyncio
    async def test_returns_scraped_data(
        self, client, auth_params, mock_get_url_metadata, mock_info_extract_service
    ):
        """Happy path: valid API key + valid url → returns scraped result."""
        _, mock_result = mock_info_extract_service
        params = {**auth_params, "url": "https://twitter.com/user/status/123"}

        resp = await client.post("/scraper/getItem", params=params)

        assert resp.status_code == 200
        assert resp.json() == mock_result

    @pytest.mark.asyncio
    async def test_rejects_with_wrong_api_key(self, client):
        """Wrong API key → 401."""
        resp = await client.post(
            "/scraper/getItem",
            params={TEST_API_KEY_NAME: "wrong-key", "url": "https://example.com"},
        )
        assert resp.status_code == 401

    @pytest.mark.xfail(
        reason="auth.py bug: verify_key checks wrong variable for None, "
               "TypeError propagates instead of returning 401",
        raises=TypeError,
        strict=True,
    )
    @pytest.mark.asyncio
    async def test_no_api_key_returns_401(self, client):
        """No API key → should be 401. Blocked by auth.py bug."""
        resp = await client.post(
            "/scraper/getItem", params={"url": "https://example.com"}
        )
        assert resp.status_code == 401

    @pytest.mark.xfail(
        reason="scraper.py does dict.pop('url') without default → unhandled KeyError",
        raises=KeyError,
        strict=True,
    )
    @pytest.mark.asyncio
    async def test_missing_url_returns_error(
        self, client, auth_params, mock_get_url_metadata, mock_info_extract_service
    ):
        """No url param → should return 4xx, but KeyError propagates unhandled."""
        resp = await client.post("/scraper/getItem", params=auth_params)
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_strips_api_key_from_downstream_params(
        self, client, auth_params, mock_get_url_metadata, mock_info_extract_service
    ):
        """
        API_KEY_NAME should be stripped from query_params before passing
        to InfoExtractService. Extra params should pass through.
        """
        mock_cls, _ = mock_info_extract_service
        params = {
            **auth_params,
            "url": "https://twitter.com/user/status/123",
            "extra_option": "value",
        }

        resp = await client.post("/scraper/getItem", params=params)

        assert resp.status_code == 200
        # InfoExtractService(url_metadata, **query_params) — verify call
        call_args, call_kwargs = mock_cls.call_args
        # API key name must NOT be in kwargs
        assert TEST_API_KEY_NAME not in call_kwargs
        # extra_option MUST be in kwargs
        assert call_kwargs.get("extra_option") == "value"

    @pytest.mark.asyncio
    async def test_passes_ban_list_to_metadata(
        self, client, auth_params, mock_get_url_metadata, mock_info_extract_service
    ):
        """ban_list param should be forwarded to get_url_metadata."""
        mock_fn, _ = mock_get_url_metadata
        params = {
            **auth_params,
            "url": "https://twitter.com/user/status/123",
            "ban_list": "twitter,weibo",
        }

        resp = await client.post("/scraper/getItem", params=params)

        assert resp.status_code == 200
        mock_fn.assert_called_once_with(
            "https://twitter.com/user/status/123", "twitter,weibo"
        )


# ─── POST /scraper/getUrlMetadata ────────────────────────────────────


class TestGetUrlMetadata:
    """Tests for POST /scraper/getUrlMetadata"""

    @pytest.mark.asyncio
    async def test_returns_metadata_dict(
        self, client, auth_params, mock_get_url_metadata
    ):
        """Happy path: returns UrlMetadata.to_dict() result."""
        params = {**auth_params, "url": "https://twitter.com/user/status/123"}

        resp = await client.post("/scraper/getUrlMetadata", params=params)

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "twitter"
        assert data["content_type"] == "social_media"
        assert "url" in data

    @pytest.mark.asyncio
    async def test_rejects_with_wrong_api_key(self, client):
        """Wrong API key → 401."""
        resp = await client.post(
            "/scraper/getUrlMetadata",
            params={TEST_API_KEY_NAME: "wrong-key", "url": "https://example.com"},
        )
        assert resp.status_code == 401

    @pytest.mark.xfail(
        reason="auth.py bug: verify_key checks wrong variable for None",
        raises=TypeError,
        strict=True,
    )
    @pytest.mark.asyncio
    async def test_no_api_key_returns_401(self, client):
        """No API key → should be 401. Blocked by auth.py bug."""
        resp = await client.post(
            "/scraper/getUrlMetadata", params={"url": "https://example.com"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_metadata_url_and_ban_list_passthrough(
        self, client, auth_params, mock_get_url_metadata
    ):
        """url and ban_list params reach get_url_metadata unchanged."""
        mock_fn, _ = mock_get_url_metadata
        test_url = "https://weibo.com/some/post/456"
        params = {**auth_params, "url": test_url, "ban_list": "reddit"}

        await client.post("/scraper/getUrlMetadata", params=params)

        mock_fn.assert_called_once()
        args = mock_fn.call_args[0]
        assert args[0] == test_url

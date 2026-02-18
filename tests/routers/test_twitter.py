"""
Tests for /twitter router endpoints.

Endpoints:
    POST /twitter/repost — Handle twitter repost webhook

NOTE: twitter router is NOT registered in production app (main.py).
      It's included in the test app via conftest.py for testing purposes.
      This is either an oversight or intentional — flag for review.

InfoExtractService is mocked — we don't make real Twitter API calls in tests.
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_API_KEY, TEST_API_KEY_NAME


class TestTwitterRepost:
    """Tests for POST /twitter/repost"""

    @pytest.mark.asyncio
    async def test_repost_returns_ok(self, client, auth_params):
        """Happy path: valid url → InfoExtractService called → returns 'ok'."""
        with patch(
            "app.routers.twitter.InfoExtractService"
        ) as MockCls:
            instance = MockCls.return_value
            instance.get_item = AsyncMock(return_value={"text": "mocked"})

            params = {**auth_params, "url": "https://twitter.com/user/status/999"}
            resp = await client.post("/twitter/repost", params=params)

            assert resp.status_code == 200
            assert resp.json() == "ok"

            # Verify InfoExtractService was constructed with correct metadata dict
            call_args = MockCls.call_args[0][0]
            assert call_args["url"] == "https://twitter.com/user/status/999"
            assert call_args["source"] == "twitter"
            assert call_args["type"] == "social_media"

            # Verify get_item was actually called
            instance.get_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_repost_rejects_wrong_api_key(self, client):
        """Wrong API key → 401."""
        resp = await client.post(
            "/twitter/repost",
            params={
                TEST_API_KEY_NAME: "totally-wrong-key",
                "url": "https://twitter.com/x/status/1",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.xfail(
        reason="auth.py bug: verify_key checks wrong variable for None",
        raises=TypeError,
        strict=True,
    )
    @pytest.mark.asyncio
    async def test_repost_no_api_key_returns_401(self, client):
        """No API key → should be 401. Blocked by auth.py bug."""
        resp = await client.post(
            "/twitter/repost",
            params={"url": "https://twitter.com/x/status/1"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_repost_missing_url(self, client, auth_params):
        """Missing url param → 422 (FastAPI validation error for required param)."""
        resp = await client.post("/twitter/repost", params=auth_params)
        assert resp.status_code == 422

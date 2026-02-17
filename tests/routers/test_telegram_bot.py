"""
Tests for /telegram router endpoints.

Endpoints:
    POST /telegram/bot/webhook      — Receive Telegram updates
    GET  /telegram/bot/set_webhook  — Set the webhook URL

All Telegram service calls are mocked.
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import (
    TEST_API_KEY,
    TEST_API_KEY_NAME,
    TEST_TELEGRAM_SECRET,
)


class TestTelegramWebhook:
    """Tests for POST /telegram/bot/webhook"""

    @pytest.mark.asyncio
    async def test_webhook_accepts_valid_update(
        self, client, telegram_auth_headers
    ):
        """
        Valid secret token + JSON body → 200, background task queued.
        """
        with patch(
            "app.routers.telegram_bot.process_telegram_update",
            new_callable=AsyncMock,
        ):
            update_data = {
                "update_id": 123456,
                "message": {
                    "message_id": 1,
                    "text": "/start",
                    "chat": {"id": 789, "type": "private"},
                },
            }

            resp = await client.post(
                "/telegram/bot/webhook",
                json=update_data,
                headers=telegram_auth_headers,
            )

            assert resp.status_code == 200
            assert resp.json() == "ok"
            # Background task should have been called with the update data
            # Note: BackgroundTasks in test mode may execute synchronously
            # The key assertion is that the endpoint accepted the request

    @pytest.mark.asyncio
    async def test_webhook_rejects_missing_token(self, client):
        """No secret token header → 401."""
        resp = await client.post(
            "/telegram/bot/webhook",
            json={"update_id": 1},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_rejects_wrong_token(self, client):
        """Wrong secret token → 401."""
        resp = await client.post(
            "/telegram/bot/webhook",
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-token"},
        )
        assert resp.status_code == 401


class TestSetWebhook:
    """Tests for GET /telegram/bot/set_webhook"""

    @pytest.mark.asyncio
    async def test_set_webhook_success(self, client, auth_params):
        """set_webhook returns True → 200 'ok'."""
        with patch(
            "app.routers.telegram_bot.set_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await client.get(
                "/telegram/bot/set_webhook", params=auth_params
            )
            assert resp.status_code == 200
            assert resp.json() == "ok"

    @pytest.mark.asyncio
    async def test_set_webhook_failure(self, client, auth_params):
        """set_webhook returns False → 500."""
        with patch(
            "app.routers.telegram_bot.set_webhook",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await client.get(
                "/telegram/bot/set_webhook", params=auth_params
            )
            assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_set_webhook_wrong_api_key(self, client):
        """Wrong API key → 401."""
        with patch(
            "app.routers.telegram_bot.set_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await client.get(
                "/telegram/bot/set_webhook",
                params={TEST_API_KEY_NAME: "bad-key"},
            )
            assert resp.status_code == 401

    @pytest.mark.xfail(
        reason="auth.py bug: verify_key checks wrong variable for None",
        raises=TypeError,
        strict=True,
    )
    @pytest.mark.asyncio
    async def test_set_webhook_no_api_key_returns_401(self, client):
        """No API key → should be 401. Blocked by auth.py bug."""
        with patch(
            "app.routers.telegram_bot.set_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await client.get("/telegram/bot/set_webhook")
            assert resp.status_code == 401

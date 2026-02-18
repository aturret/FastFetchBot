"""
Tests for the telegram-bot webhook endpoint.

Verifies:
    - Auth: valid/missing/wrong secret token handling
    - Processing: updates are dispatched via asyncio.create_task (fire-and-forget)
    - Response: 200 with {"status": "ok"} for valid requests
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_TELEGRAM_SECRET


SAMPLE_UPDATE = {
    "update_id": 123456,
    "message": {
        "message_id": 1,
        "text": "/start",
        "chat": {"id": 789, "type": "private"},
    },
}


class TestTelegramWebhook:
    """Tests for POST /webhook"""

    @pytest.mark.asyncio
    async def test_webhook_accepts_valid_update(self, client, telegram_auth_headers):
        """Valid secret token + JSON body -> 200, process_telegram_update is called."""
        with patch(
            "core.webhook.server.process_telegram_update",
            new_callable=AsyncMock,
        ) as mock_process:
            resp = await client.post(
                "/webhook",
                json=SAMPLE_UPDATE,
                headers=telegram_auth_headers,
            )

            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # Allow the create_task coroutine to run
            await asyncio.sleep(0)
            mock_process.assert_called_once_with(SAMPLE_UPDATE)

    @pytest.mark.asyncio
    async def test_webhook_rejects_missing_token(self, client):
        """No secret token header -> 401."""
        resp = await client.post("/webhook", json=SAMPLE_UPDATE)
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}

    @pytest.mark.asyncio
    async def test_webhook_rejects_wrong_token(self, client):
        """Wrong secret token -> 401."""
        resp = await client.post(
            "/webhook",
            json=SAMPLE_UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-token"},
        )
        assert resp.status_code == 401
        assert resp.json() == {"error": "unauthorized"}

    @pytest.mark.asyncio
    async def test_webhook_responds_before_processing_completes(
        self, client, telegram_auth_headers
    ):
        """
        The webhook must return 200 immediately, before the update
        processing finishes. This is the fire-and-forget behavior that
        prevents Telegram from timing out on slow handlers.
        """
        processing_started = asyncio.Event()
        processing_gate = asyncio.Event()

        async def slow_process(data):
            processing_started.set()
            await processing_gate.wait()  # Block until test releases

        with patch(
            "core.webhook.server.process_telegram_update",
            side_effect=slow_process,
        ):
            resp = await client.post(
                "/webhook",
                json=SAMPLE_UPDATE,
                headers=telegram_auth_headers,
            )

            # Response arrived while processing is still blocked
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # Let the background task finish to avoid warnings
            processing_gate.set()
            await asyncio.sleep(0)

"""Tests for apps/telegram-bot/core/webhook/server.py"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLogTaskException:
    def test_logs_exception_from_failed_task(self):
        from core.webhook.server import _log_task_exception

        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.cancelled.return_value = False
        test_exc = RuntimeError("task boom")
        mock_task.exception.return_value = test_exc

        with patch("core.webhook.server.logger") as mock_logger:
            _log_task_exception(mock_task)
            mock_logger.exception.assert_called_once()

    def test_does_not_log_cancelled_task(self):
        from core.webhook.server import _log_task_exception

        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.cancelled.return_value = True

        with patch("core.webhook.server.logger") as mock_logger:
            _log_task_exception(mock_task)
            mock_logger.exception.assert_not_called()

    def test_does_not_log_successful_task(self):
        from core.webhook.server import _log_task_exception

        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = None

        with patch("core.webhook.server.logger") as mock_logger:
            _log_task_exception(mock_task)
            mock_logger.exception.assert_not_called()


class TestTelegramWebhook:
    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self):
        from core.webhook.server import telegram_webhook

        mock_request = MagicMock()
        mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": ""}
        mock_request.json = AsyncMock(side_effect=ValueError("bad json"))

        with patch("core.webhook.server.settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_SECRET_TOKEN = ""
            response = await telegram_webhook(mock_request)
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_unauthorized_returns_401(self):
        from core.webhook.server import telegram_webhook

        mock_request = MagicMock()
        mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong"}

        with patch("core.webhook.server.settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_SECRET_TOKEN = "correct"
            response = await telegram_webhook(mock_request)
            assert response.status_code == 401


class TestSendMessageEndpoint:
    @pytest.mark.asyncio
    async def test_exception_returns_500(self):
        from core.webhook.server import send_message_endpoint

        mock_request = MagicMock()
        mock_request.json = AsyncMock(side_effect=RuntimeError("db error"))

        response = await send_message_endpoint(mock_request)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_success_returns_ok(self):
        from core.webhook.server import send_message_endpoint

        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={
            "data": {"title": "test"},
            "chat_id": "123",
        })

        with patch("core.webhook.server.send_item_message", new_callable=AsyncMock):
            response = await send_message_endpoint(mock_request)
            assert response.status_code == 200

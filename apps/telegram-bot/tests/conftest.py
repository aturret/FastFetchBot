"""
Test fixtures for the telegram-bot app.

All bot service calls are mocked — tests verify routing, auth, and
request handling without touching the real Telegram API.
"""

import os

import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport

TEST_TELEGRAM_SECRET = "test-telegram-secret-token"

os.environ["TELEGRAM_BOT_SECRET_TOKEN"] = TEST_TELEGRAM_SECRET
os.environ["TELEGRAM_BOT_TOKEN"] = "000000000:AAFakeTokenForTesting"
os.environ["DATABASE_ON"] = "false"
os.environ["BASE_URL"] = "localhost"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="module")
async def app():
    """
    Create a Starlette webhook_app with a no-op lifespan
    so we can test routes without real bot initialization.
    """
    @asynccontextmanager
    async def mock_lifespan(app):
        yield

    with patch("core.webhook.server.lifespan", mock_lifespan):
        from starlette.applications import Starlette
        from starlette.routing import Route
        from core.webhook.server import telegram_webhook, send_message_endpoint, health

        test_app = Starlette(
            routes=[
                Route("/webhook", telegram_webhook, methods=["POST"]),
                Route("/send_message", send_message_endpoint, methods=["POST"]),
                Route("/health", health, methods=["GET"]),
            ],
            lifespan=mock_lifespan,
        )
        yield test_app


@pytest_asyncio.fixture(scope="module")
async def client(app):
    """Async HTTP client hitting the Starlette app via ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def telegram_auth_headers():
    """Headers dict with valid Telegram secret token."""
    return {"X-Telegram-Bot-Api-Secret-Token": TEST_TELEGRAM_SECRET}

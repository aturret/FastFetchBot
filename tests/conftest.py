"""
Global test fixtures for FastFetchBot.

Core philosophy: router tests mock ALL downstream services.
We test the routing logic, auth, and request parsing — not the scrapers themselves.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient, ASGITransport

# We must set env vars BEFORE importing app modules,
# otherwise config.py reads os.environ at import time
# and we lose control over API_KEY / secret tokens.
import os

TEST_API_KEY = "test-api-key-for-unit-tests"
TEST_API_KEY_NAME = "pwd"
TEST_TELEGRAM_SECRET = "test-telegram-secret-token"
TEST_TELEGRAM_BOT_TOKEN = "000000000:AAFakeTokenForTesting"

os.environ["API_KEY"] = TEST_API_KEY
os.environ["API_KEY_NAME"] = TEST_API_KEY_NAME
os.environ["TELEGRAM_BOT_SECRET_TOKEN"] = TEST_TELEGRAM_SECRET
os.environ["TELEGRAM_BOT_TOKEN"] = TEST_TELEGRAM_BOT_TOKEN
os.environ["DATABASE_ON"] = "false"
os.environ["BASE_URL"] = "localhost"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="module")
async def app():
    """
    Create a fresh FastAPI app for testing.

    We mock out the lifespan to avoid real Telegram webhook setup
    and database connections during tests. Tests should be fast and
    isolated — no network, no DB.

    Also includes twitter and feed_push routers which are defined
    but not registered in the production app — we want to test them anyway.
    """
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    @asynccontextmanager
    async def mock_lifespan(app: FastAPI):
        yield

    # Patch lifespan before creating the app
    with patch("app.main.lifespan", mock_lifespan):
        from app.main import create_app
        from app.routers.twitter import router as twitter_router
        from app.routers.feed_push import router as feed_push_router

        test_app = create_app()
        # Override lifespan on the created app
        test_app.router.lifespan_context = mock_lifespan

        # Include routers that exist but aren't registered in production app
        test_app.include_router(twitter_router)
        test_app.include_router(feed_push_router)

        yield test_app


@pytest_asyncio.fixture(scope="module")
async def client(app):
    """
    Async HTTP client hitting the FastAPI app directly via ASGI transport.
    No real HTTP server needed. Fast.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_params():
    """Query params dict with valid API key. Use for authenticated requests."""
    return {TEST_API_KEY_NAME: TEST_API_KEY}


@pytest.fixture
def telegram_auth_headers():
    """Headers dict with valid Telegram secret token."""
    return {"X-Telegram-Bot-Api-Secret-Token": TEST_TELEGRAM_SECRET}


@pytest.fixture
def mock_info_extract_service():
    """
    Mock InfoExtractService at the scraper.py import site.

    IMPORTANT: patch where it's USED, not where it's DEFINED.
    The router does `from app.services.scrapers.common import InfoExtractService`
    so the name is bound in the router module's namespace.
    """
    mock_result = {
        "text": "mocked scraped content",
        "media": [],
        "source": "test",
    }
    with patch(
        "app.routers.scraper.InfoExtractService"
    ) as MockClass:
        instance = MockClass.return_value
        instance.get_item = AsyncMock(return_value=mock_result)
        yield MockClass, mock_result


@pytest.fixture
def mock_get_url_metadata():
    """
    Mock get_url_metadata so we control what UrlMetadata is returned.
    """
    from app.models.url_metadata import UrlMetadata

    fake_metadata = UrlMetadata(
        url="https://example.com/post/123",
        source="twitter",
        content_type="social_media",
    )
    with patch(
        "app.routers.scraper.get_url_metadata",
        new_callable=AsyncMock,
        return_value=fake_metadata,
    ) as mock:
        yield mock, fake_metadata

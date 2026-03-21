import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastfetchbot_shared.models.url_metadata import UrlMetadata


@pytest.fixture
def make_url_metadata():
    """Factory fixture to create UrlMetadata instances."""

    def _make(source="twitter", url="https://example.com", content_type=""):
        return UrlMetadata(url=url, source=source, content_type=content_type)

    return _make


@pytest.fixture
def sample_metadata_item_dict():
    """Minimal valid metadata_item dict."""
    return {
        "url": "https://example.com/post/1",
        "telegraph_url": "",
        "content": "<p>Test content</p>",
        "text": "Test content",
        "media_files": [],
        "author": "testuser",
        "title": "Test Title",
        "author_url": "https://example.com/testuser",
        "category": "twitter",
        "message_type": "short",
    }


@pytest.fixture(autouse=True)
def reset_scraper_manager():
    """Reset ScraperManager class-level state after each test."""
    yield
    from fastfetchbot_shared.services.scrapers.scraper_manager import ScraperManager

    ScraperManager.bluesky_scraper = None
    ScraperManager.weibo_scraper = None
    ScraperManager.general_scraper = None
    ScraperManager.scrapers = {
        "bluesky": None,
        "weibo": None,
        "other": None,
        "unknown": None,
    }


@pytest.fixture
def mock_jinja2_env():
    """Patch JINJA2_ENV to return a mock template."""
    mock_template = MagicMock()
    mock_template.render.return_value = "<p>rendered</p>"
    mock_env = MagicMock()
    mock_env.get_template.return_value = mock_template
    with patch(
        "fastfetchbot_shared.services.scrapers.config.JINJA2_ENV", mock_env
    ) as m:
        yield m


@pytest.fixture
def mock_get_response_json():
    """Patch network.get_response_json."""
    with patch(
        "fastfetchbot_shared.utils.network.get_response_json", new_callable=AsyncMock
    ) as m:
        yield m


@pytest.fixture
def mock_get_selector():
    """Patch network.get_selector."""
    with patch(
        "fastfetchbot_shared.utils.network.get_selector", new_callable=AsyncMock
    ) as m:
        yield m


@pytest.fixture
def mock_get_response():
    """Patch network.get_response."""
    with patch(
        "fastfetchbot_shared.utils.network.get_response", new_callable=AsyncMock
    ) as m:
        yield m


@pytest.fixture
def mock_get_redirect_url():
    """Patch network.get_redirect_url."""
    with patch(
        "fastfetchbot_shared.utils.network.get_redirect_url", new_callable=AsyncMock
    ) as m:
        yield m

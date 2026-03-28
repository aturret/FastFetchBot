"""Tests for packages/shared/fastfetchbot_shared/services/scrapers/scraper_manager.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.services.scrapers.scraper_manager import ScraperManager
from fastfetchbot_shared.exceptions import ScraperError


# ---------------------------------------------------------------------------
# init_scrapers
# ---------------------------------------------------------------------------

class TestInitScrapers:
    @pytest.mark.asyncio
    async def test_init_scrapers_calls_init_bluesky(self):
        with patch.object(
            ScraperManager, "init_bluesky_scraper", new_callable=AsyncMock
        ) as mock_init:
            mock_init.return_value = MagicMock()
            await ScraperManager.init_scrapers()
            mock_init.assert_awaited_once()


# ---------------------------------------------------------------------------
# init_scraper — bluesky
# ---------------------------------------------------------------------------

class TestInitScraperBluesky:
    @pytest.mark.asyncio
    async def test_init_bluesky_when_not_initialized(self):
        mock_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_bluesky_scraper", new_callable=AsyncMock,
            return_value=mock_scraper,
        ):
            await ScraperManager.init_scraper("bluesky")
            assert ScraperManager.scrapers["bluesky"] is mock_scraper

    @pytest.mark.asyncio
    async def test_init_bluesky_when_already_initialized(self):
        ScraperManager.bluesky_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_bluesky_scraper", new_callable=AsyncMock,
        ) as mock_init:
            await ScraperManager.init_scraper("bluesky")
            mock_init.assert_not_awaited()


# ---------------------------------------------------------------------------
# init_scraper — weibo
# ---------------------------------------------------------------------------

class TestInitScraperWeibo:
    @pytest.mark.asyncio
    async def test_init_weibo_when_not_initialized(self):
        mock_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_weibo_scraper", new_callable=AsyncMock,
            return_value=mock_scraper,
        ):
            await ScraperManager.init_scraper("weibo")
            assert ScraperManager.scrapers["weibo"] is mock_scraper

    @pytest.mark.asyncio
    async def test_init_weibo_when_already_initialized(self):
        ScraperManager.weibo_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_weibo_scraper", new_callable=AsyncMock,
        ) as mock_init:
            await ScraperManager.init_scraper("weibo")
            mock_init.assert_not_awaited()


# ---------------------------------------------------------------------------
# init_scraper — other / unknown (general scraper)
# ---------------------------------------------------------------------------

class TestInitScraperGeneral:
    @pytest.mark.asyncio
    async def test_init_other_when_not_initialized(self):
        mock_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_general_scraper", new_callable=AsyncMock,
            return_value=mock_scraper,
        ):
            await ScraperManager.init_scraper("other")
            assert ScraperManager.scrapers["other"] is mock_scraper
            assert ScraperManager.scrapers["unknown"] is mock_scraper

    @pytest.mark.asyncio
    async def test_init_unknown_when_not_initialized(self):
        mock_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_general_scraper", new_callable=AsyncMock,
            return_value=mock_scraper,
        ):
            await ScraperManager.init_scraper("unknown")
            assert ScraperManager.scrapers["other"] is mock_scraper
            assert ScraperManager.scrapers["unknown"] is mock_scraper

    @pytest.mark.asyncio
    async def test_init_other_when_already_initialized(self):
        ScraperManager.general_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_general_scraper", new_callable=AsyncMock,
        ) as mock_init:
            await ScraperManager.init_scraper("other")
            mock_init.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_init_unknown_when_already_initialized(self):
        ScraperManager.general_scraper = MagicMock()
        with patch.object(
            ScraperManager, "init_general_scraper", new_callable=AsyncMock,
        ) as mock_init:
            await ScraperManager.init_scraper("unknown")
            mock_init.assert_not_awaited()


# ---------------------------------------------------------------------------
# init_scraper — unsupported category
# ---------------------------------------------------------------------------

class TestInitScraperUnsupported:
    @pytest.mark.asyncio
    async def test_unsupported_category_raises_scraper_error(self):
        with pytest.raises(ScraperError, match="not supported"):
            await ScraperManager.init_scraper("tiktok")


# ---------------------------------------------------------------------------
# init_bluesky_scraper
# ---------------------------------------------------------------------------

class TestInitBlueskyScraperDirect:
    @pytest.mark.asyncio
    async def test_creates_and_inits_bluesky_scraper(self):
        mock_instance = MagicMock()
        mock_instance.init = AsyncMock()

        with patch(
            "fastfetchbot_shared.services.scrapers.scraper_manager.BlueskyScraper",
            return_value=mock_instance,
        ) as MockCls, patch(
            "fastfetchbot_shared.services.scrapers.config.settings.BLUESKY_USERNAME",
            "testuser",
        ), patch(
            "fastfetchbot_shared.services.scrapers.config.settings.BLUESKY_PASSWORD",
            "testpass",
        ):
            result = await ScraperManager.init_bluesky_scraper()

        MockCls.assert_called_once_with(username="testuser", password="testpass")
        mock_instance.init.assert_awaited_once()
        assert result is mock_instance
        assert ScraperManager.bluesky_scraper is mock_instance


# ---------------------------------------------------------------------------
# init_weibo_scraper
# ---------------------------------------------------------------------------

class TestInitWeiboScraperDirect:
    @pytest.mark.asyncio
    async def test_creates_weibo_scraper(self):
        mock_instance = MagicMock()

        with patch(
            "fastfetchbot_shared.services.scrapers.scraper_manager.WeiboScraper",
            return_value=mock_instance,
        ) as MockCls:
            result = await ScraperManager.init_weibo_scraper()

        MockCls.assert_called_once_with()
        assert result is mock_instance
        assert ScraperManager.weibo_scraper is mock_instance


# ---------------------------------------------------------------------------
# init_general_scraper
# ---------------------------------------------------------------------------

class TestInitGeneralScraperDirect:
    @pytest.mark.asyncio
    async def test_creates_general_scraper(self):
        mock_instance = MagicMock()

        with patch(
            "fastfetchbot_shared.services.scrapers.scraper_manager.GeneralScraper",
            return_value=mock_instance,
        ) as MockCls:
            result = await ScraperManager.init_general_scraper()

        MockCls.assert_called_once_with()
        assert result is mock_instance
        assert ScraperManager.general_scraper is mock_instance

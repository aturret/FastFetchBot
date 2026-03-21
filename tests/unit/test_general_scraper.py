"""Tests for packages/shared/fastfetchbot_shared/services/scrapers/general/scraper.py"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from fastfetchbot_shared.services.scrapers.general.scraper import GeneralScraper
from fastfetchbot_shared.services.scrapers.general.firecrawl import FirecrawlScraper
from fastfetchbot_shared.services.scrapers.general.zyte import ZyteScraper
from fastfetchbot_shared.services.scrapers.general.base import BaseGeneralScraper


# ---------------------------------------------------------------------------
# SCRAPER_REGISTRY
# ---------------------------------------------------------------------------


class TestScraperRegistry:
    def test_default_registry_has_firecrawl_and_zyte(self):
        assert "FIRECRAWL" in GeneralScraper.SCRAPER_REGISTRY
        assert "ZYTE" in GeneralScraper.SCRAPER_REGISTRY
        assert GeneralScraper.SCRAPER_REGISTRY["FIRECRAWL"] is FirecrawlScraper
        assert GeneralScraper.SCRAPER_REGISTRY["ZYTE"] is ZyteScraper


# ---------------------------------------------------------------------------
# __init__ / _init_scraper
# ---------------------------------------------------------------------------


class TestGeneralScraperInit:
    @patch(
        "fastfetchbot_shared.services.scrapers.general.scraper.GENERAL_SCRAPING_API",
        "FIRECRAWL",
    )
    @patch(
        "fastfetchbot_shared.services.scrapers.general.firecrawl_client.FirecrawlClient.get_instance"
    )
    def test_default_type_from_config(self, mock_fc_instance):
        """When no scraper_type is passed, uses GENERAL_SCRAPING_API env var."""
        mock_fc_instance.return_value = MagicMock()
        gs = GeneralScraper()
        assert gs.scraper_type == "FIRECRAWL"
        assert isinstance(gs._scraper, FirecrawlScraper)

    @patch(
        "fastfetchbot_shared.services.scrapers.general.firecrawl_client.FirecrawlClient.get_instance"
    )
    def test_custom_type_firecrawl(self, mock_fc_instance):
        mock_fc_instance.return_value = MagicMock()
        gs = GeneralScraper(scraper_type="firecrawl")
        assert gs.scraper_type == "firecrawl"
        assert isinstance(gs._scraper, FirecrawlScraper)

    def test_custom_type_zyte(self):
        gs = GeneralScraper(scraper_type="ZYTE")
        assert gs.scraper_type == "ZYTE"
        assert isinstance(gs._scraper, ZyteScraper)

    @patch(
        "fastfetchbot_shared.services.scrapers.general.firecrawl_client.FirecrawlClient.get_instance"
    )
    def test_unknown_type_falls_back_to_firecrawl(self, mock_fc_instance):
        mock_fc_instance.return_value = MagicMock()
        gs = GeneralScraper(scraper_type="UNKNOWN_SCRAPER")
        # Should fall back to FirecrawlScraper
        assert isinstance(gs._scraper, FirecrawlScraper)


# ---------------------------------------------------------------------------
# get_processor_by_url
# ---------------------------------------------------------------------------


class TestGetProcessorByUrl:
    @pytest.mark.asyncio
    async def test_delegates_to_underlying_scraper(self):
        gs = GeneralScraper(scraper_type="ZYTE")
        processor = await gs.get_processor_by_url("https://example.com")
        from fastfetchbot_shared.services.scrapers.general.zyte import ZyteDataProcessor
        assert isinstance(processor, ZyteDataProcessor)


# ---------------------------------------------------------------------------
# register_scraper / get_available_scrapers
# ---------------------------------------------------------------------------


class TestRegisterAndGetAvailable:
    def test_register_scraper(self):
        class FakeScraper(BaseGeneralScraper):
            async def get_processor_by_url(self, url):
                pass

        original_registry = dict(GeneralScraper.SCRAPER_REGISTRY)
        try:
            GeneralScraper.register_scraper("FAKE", FakeScraper)
            assert "FAKE" in GeneralScraper.SCRAPER_REGISTRY
            assert GeneralScraper.SCRAPER_REGISTRY["FAKE"] is FakeScraper
        finally:
            GeneralScraper.SCRAPER_REGISTRY = original_registry

    def test_register_scraper_uppercases_name(self):
        class FakeScraper2(BaseGeneralScraper):
            async def get_processor_by_url(self, url):
                pass

        original_registry = dict(GeneralScraper.SCRAPER_REGISTRY)
        try:
            GeneralScraper.register_scraper("lowercase", FakeScraper2)
            assert "LOWERCASE" in GeneralScraper.SCRAPER_REGISTRY
        finally:
            GeneralScraper.SCRAPER_REGISTRY = original_registry

    def test_get_available_scrapers(self):
        scrapers = GeneralScraper.get_available_scrapers()
        assert isinstance(scrapers, list)
        assert "FIRECRAWL" in scrapers
        assert "ZYTE" in scrapers

from typing import Optional

from src.config import GENERAL_SCRAPING_API
from src.services.scrapers.scraper import Scraper, DataProcessor
from src.services.scrapers.general.base import BaseGeneralScraper
from src.services.scrapers.general.firecrawl import FirecrawlScraper
from src.services.scrapers.general.zyte import ZyteScraper
from fastfetchbot_shared.utils.logger import logger


class GeneralScraper(Scraper):
    """
    GeneralScraper: A wrapper scraper that delegates to the configured scraper implementation.

    This class acts as a factory/facade that selects the appropriate scraper
    based on the GENERAL_SCRAPING_API configuration.

    Supported scrapers:
    - FIRECRAWL: Uses Firecrawl API for scraping
    - ZYTE: Uses Zyte API for scraping
    """

    # Registry of available scrapers
    SCRAPER_REGISTRY: dict[str, type[BaseGeneralScraper]] = {
        "FIRECRAWL": FirecrawlScraper,
        "ZYTE": ZyteScraper,
    }

    def __init__(self, scraper_type: Optional[str] = None):
        """
        Initialize the GeneralScraper with a specific scraper type.

        Args:
            scraper_type: The type of scraper to use. If None, uses GENERAL_SCRAPING_API config.
        """
        self.scraper_type = scraper_type or GENERAL_SCRAPING_API
        self._scraper: Optional[BaseGeneralScraper] = None
        self._init_scraper()

    def _init_scraper(self) -> None:
        """Initialize the underlying scraper based on scraper_type."""
        scraper_class = self.SCRAPER_REGISTRY.get(self.scraper_type.upper())

        if scraper_class is None:
            available = ", ".join(self.SCRAPER_REGISTRY.keys())
            logger.error(f"Unknown scraper type: {self.scraper_type}. Available: {available}")
            # Fall back to Firecrawl as default
            logger.info("Falling back to FIRECRAWL scraper")
            scraper_class = FirecrawlScraper

        self._scraper = scraper_class()
        logger.info(f"Initialized GeneralScraper with {self.scraper_type} backend")

    async def get_processor_by_url(self, url: str) -> DataProcessor:
        """
        Get the appropriate data processor for the given URL.

        Args:
            url: The URL to scrape

        Returns:
            DataProcessor instance for processing the URL
        """
        return await self._scraper.get_processor_by_url(url)

    @classmethod
    def register_scraper(cls, name: str, scraper_class: type[BaseGeneralScraper]) -> None:
        """
        Register a new scraper type.

        Args:
            name: The name to register the scraper under (e.g., "ZYTE")
            scraper_class: The scraper class to register
        """
        cls.SCRAPER_REGISTRY[name.upper()] = scraper_class
        logger.info(f"Registered new scraper: {name}")

    @classmethod
    def get_available_scrapers(cls) -> list[str]:
        """
        Get a list of available scraper types.

        Returns:
            List of registered scraper names
        """
        return list(cls.SCRAPER_REGISTRY.keys())

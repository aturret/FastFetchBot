"""Tests for the Scraper and DataProcessor abstract base classes.

Note: These classes use @abstractmethod but do not inherit from ABC,
so Python does not enforce instantiation restrictions. The abstract
methods serve as documentation of the interface contract.
"""

import pytest

from fastfetchbot_shared.services.scrapers.scraper import DataProcessor, Scraper


class TestScraperABC:
    """Tests for the Scraper abstract base class."""

    def test_base_class_instantiates_without_abc(self):
        """Scraper can be instantiated since it does not inherit from ABC."""
        scraper = Scraper()
        assert scraper is not None

    def test_get_processor_by_url_is_abstract(self):
        """get_processor_by_url is decorated with @abstractmethod."""
        assert getattr(Scraper.get_processor_by_url, "__isabstractmethod__", False)

    def test_concrete_subclass_can_be_instantiated(self):
        """A subclass implementing the abstract method can be instantiated."""

        class ConcreteScraper(Scraper):
            async def get_processor_by_url(self, url) -> object:
                return {"url": url}

        scraper = ConcreteScraper()
        assert scraper is not None

    @pytest.mark.asyncio
    async def test_concrete_subclass_method_works(self):
        """The implemented method is callable and returns expected value."""

        class ConcreteScraper(Scraper):
            async def get_processor_by_url(self, url) -> object:
                return {"url": url}

        scraper = ConcreteScraper()
        result = await scraper.get_processor_by_url("https://example.com")
        assert result == {"url": "https://example.com"}

    @pytest.mark.asyncio
    async def test_base_get_processor_by_url_returns_none(self):
        """Calling the base abstract method directly returns None (pass body)."""
        scraper = Scraper()
        result = await scraper.get_processor_by_url("https://example.com")
        assert result is None


class TestDataProcessorABC:
    """Tests for the DataProcessor abstract base class."""

    def test_base_class_instantiates_without_abc(self):
        """DataProcessor can be instantiated since it does not inherit from ABC."""
        processor = DataProcessor()
        assert processor is not None

    def test_get_item_is_abstract(self):
        """get_item is decorated with @abstractmethod."""
        assert getattr(DataProcessor.get_item, "__isabstractmethod__", False)

    def test_process_data_is_abstract(self):
        """process_data is decorated with @abstractmethod."""
        assert getattr(DataProcessor.process_data, "__isabstractmethod__", False)

    def test_concrete_subclass_can_be_instantiated(self):
        """A subclass implementing all abstract methods can be instantiated."""

        class ConcreteProcessor(DataProcessor):
            async def get_item(self) -> dict:
                return {"key": "value"}

            async def process_data(self) -> None:
                pass

        processor = ConcreteProcessor()
        assert processor is not None

    @pytest.mark.asyncio
    async def test_concrete_subclass_get_item_works(self):
        """The implemented get_item method returns the expected value."""

        class ConcreteProcessor(DataProcessor):
            async def get_item(self) -> dict:
                return {"key": "value"}

            async def process_data(self) -> None:
                pass

        processor = ConcreteProcessor()
        result = await processor.get_item()
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_concrete_subclass_process_data_works(self):
        """The implemented process_data method executes correctly."""

        class ConcreteProcessor(DataProcessor):
            self_processed = False

            async def get_item(self) -> dict:
                return {}

            async def process_data(self) -> None:
                self.self_processed = True

        processor = ConcreteProcessor()
        await processor.process_data()
        assert processor.self_processed is True

    @pytest.mark.asyncio
    async def test_base_get_item_returns_none(self):
        """Calling the base get_item directly returns None (pass body)."""
        processor = DataProcessor()
        result = await processor.get_item()
        assert result is None

    @pytest.mark.asyncio
    async def test_base_process_data_returns_none(self):
        """Calling the base process_data directly returns None (pass body)."""
        processor = DataProcessor()
        result = await processor.process_data()
        assert result is None

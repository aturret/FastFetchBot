from abc import abstractmethod


class Scraper:

    @abstractmethod
    async def get_processor_by_url(self, url) -> object:
        pass


class DataProcessor:

    @abstractmethod
    async def get_item(self) -> dict:
        pass

    @abstractmethod
    async def process_data(self) -> None:
        pass

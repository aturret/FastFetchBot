class FastFetchBotError(Exception):
    """Base exception for all FastFetchBot domain errors."""


class ScraperError(FastFetchBotError):
    """Error during scraping."""


class ScraperNetworkError(ScraperError):
    """Network/connection error during scraping."""


class ScraperParseError(ScraperError):
    """Failed to parse scraped content."""


class TelegraphPublishError(FastFetchBotError):
    """Telegraph publishing failed."""


class FileExportError(FastFetchBotError):
    """File export (PDF, video, audio) failed."""


class ExternalServiceError(FastFetchBotError):
    """External service call failed (OpenAI, Inoreader, etc.)."""

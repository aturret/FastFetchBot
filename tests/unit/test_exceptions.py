"""Tests for packages/shared/fastfetchbot_shared/exceptions.py"""

import pytest

from fastfetchbot_shared.exceptions import (
    FastFetchBotError,
    ScraperError,
    ScraperNetworkError,
    ScraperParseError,
    TelegraphPublishError,
    FileExportError,
    ExternalServiceError,
)


class TestExceptionHierarchy:
    def test_scraper_error_is_fastfetchbot_error(self):
        assert issubclass(ScraperError, FastFetchBotError)

    def test_scraper_network_error_is_scraper_error(self):
        assert issubclass(ScraperNetworkError, ScraperError)

    def test_scraper_parse_error_is_scraper_error(self):
        assert issubclass(ScraperParseError, ScraperError)

    def test_telegraph_publish_error_is_fastfetchbot_error(self):
        assert issubclass(TelegraphPublishError, FastFetchBotError)

    def test_file_export_error_is_fastfetchbot_error(self):
        assert issubclass(FileExportError, FastFetchBotError)

    def test_external_service_error_is_fastfetchbot_error(self):
        assert issubclass(ExternalServiceError, FastFetchBotError)

    def test_all_are_exceptions(self):
        for cls in (
            FastFetchBotError,
            ScraperError,
            ScraperNetworkError,
            ScraperParseError,
            TelegraphPublishError,
            FileExportError,
            ExternalServiceError,
        ):
            assert issubclass(cls, Exception)


class TestExceptionCatching:
    """Verify that catching a parent also catches children."""

    def test_catch_fastfetchbot_catches_scraper_error(self):
        with pytest.raises(FastFetchBotError):
            raise ScraperError("test")

    def test_catch_scraper_catches_network_error(self):
        with pytest.raises(ScraperError):
            raise ScraperNetworkError("network fail")

    def test_catch_scraper_catches_parse_error(self):
        with pytest.raises(ScraperError):
            raise ScraperParseError("parse fail")

    def test_catch_fastfetchbot_catches_file_export_error(self):
        with pytest.raises(FastFetchBotError):
            raise FileExportError("export fail")

    def test_catch_fastfetchbot_catches_external_service_error(self):
        with pytest.raises(FastFetchBotError):
            raise ExternalServiceError("service fail")


class TestExceptionChaining:
    def test_from_preserves_original_cause(self):
        original = ValueError("original")
        try:
            raise ScraperError("wrapped") from original
        except ScraperError as e:
            assert e.__cause__ is original

    def test_message_preserved(self):
        exc = ScraperParseError("bad data")
        assert str(exc) == "bad data"

"""Tests for FastAPI global exception handlers in apps/api/src/main.py

Uses a minimal FastAPI app with the same exception handlers to avoid
needing to fully configure the real app's dependencies.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastfetchbot_shared.exceptions import (
    FastFetchBotError,
    ScraperError,
    ScraperParseError,
    FileExportError,
)


def _create_test_app():
    """Create a minimal FastAPI app with the same exception handlers as main.py."""
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from fastfetchbot_shared.utils.logger import logger

    app = FastAPI()

    @app.exception_handler(FastFetchBotError)
    async def fastfetchbot_error_handler(request: Request, exc: FastFetchBotError):
        logger.error(f"Domain error on {request.method} {request.url}: {exc}")
        return JSONResponse(status_code=502, content={"error": str(exc)})

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.method} {request.url}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    return app


@pytest.fixture
def test_app():
    return _create_test_app()


@pytest.fixture
def client(test_app):
    return TestClient(test_app, raise_server_exceptions=False)


class TestFastFetchBotErrorHandler:
    def test_scraper_error_returns_502(self, test_app, client):
        @test_app.get("/test")
        async def _():
            raise ScraperError("Twitter API failed")

        response = client.get("/test")
        assert response.status_code == 502
        assert "Twitter API failed" in response.json()["error"]

    def test_scraper_parse_error_returns_502(self, test_app, client):
        @test_app.get("/test-parse")
        async def _():
            raise ScraperParseError("Invalid response")

        response = client.get("/test-parse")
        assert response.status_code == 502

    def test_file_export_error_returns_502(self, test_app, client):
        @test_app.get("/test-export")
        async def _():
            raise FileExportError("PDF failed")

        response = client.get("/test-export")
        assert response.status_code == 502
        assert "PDF failed" in response.json()["error"]


class TestGenericExceptionHandler:
    def test_unhandled_exception_returns_500(self, test_app, client):
        @test_app.get("/test-crash")
        async def _():
            raise RuntimeError("unexpected crash")

        response = client.get("/test-crash")
        assert response.status_code == 500
        assert response.json()["error"] == "Internal server error"

    def test_generic_does_not_leak_details(self, test_app, client):
        @test_app.get("/test-sensitive")
        async def _():
            raise ValueError("secret database password")

        response = client.get("/test-sensitive")
        assert response.status_code == 500
        assert "secret" not in response.json()["error"]

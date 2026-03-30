"""Tests for WorkerSettings on_startup / on_shutdown MongoDB lifecycle hooks."""

from unittest.mock import AsyncMock, patch

import pytest

from async_worker.main import WorkerSettings


# ---------------------------------------------------------------------------
# on_startup
# ---------------------------------------------------------------------------


class TestWorkerStartup:
    @pytest.mark.asyncio
    async def test_init_mongodb_called_when_database_on(self):
        with patch("async_worker.main.settings") as mock_settings, \
             patch(
                 "fastfetchbot_shared.database.mongodb.init_mongodb",
                 new_callable=AsyncMock,
             ) as mock_init:
            mock_settings.DATABASE_ON = True
            mock_settings.MONGODB_URL = "mongodb://localhost:27017"

            await WorkerSettings.on_startup({})

        mock_init.assert_awaited_once_with("mongodb://localhost:27017")

    @pytest.mark.asyncio
    async def test_init_mongodb_skipped_when_database_off(self):
        with patch("async_worker.main.settings") as mock_settings, \
             patch(
                 "fastfetchbot_shared.database.mongodb.init_mongodb",
                 new_callable=AsyncMock,
             ) as mock_init:
            mock_settings.DATABASE_ON = False

            await WorkerSettings.on_startup({})

        mock_init.assert_not_awaited()


# ---------------------------------------------------------------------------
# on_shutdown
# ---------------------------------------------------------------------------


class TestWorkerShutdown:
    @pytest.mark.asyncio
    async def test_close_mongodb_called_when_database_on(self):
        with patch("async_worker.main.settings") as mock_settings, \
             patch(
                 "fastfetchbot_shared.database.mongodb.close_mongodb",
                 new_callable=AsyncMock,
             ) as mock_close:
            mock_settings.DATABASE_ON = True

            await WorkerSettings.on_shutdown({})

        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_mongodb_skipped_when_database_off(self):
        with patch("async_worker.main.settings") as mock_settings, \
             patch(
                 "fastfetchbot_shared.database.mongodb.close_mongodb",
                 new_callable=AsyncMock,
             ) as mock_close:
            mock_settings.DATABASE_ON = False

            await WorkerSettings.on_shutdown({})

        mock_close.assert_not_awaited()

"""Tests for packages/shared/fastfetchbot_shared/database/mongodb/connection.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset the module-level _client before each test."""
    from fastfetchbot_shared.database.mongodb import connection

    connection._client = None
    yield
    connection._client = None


# ---------------------------------------------------------------------------
# init_mongodb
# ---------------------------------------------------------------------------


class TestInitMongodb:
    @pytest.mark.asyncio
    async def test_creates_motor_client_and_calls_init_beanie(self):
        with patch(
            "fastfetchbot_shared.database.mongodb.connection.AsyncIOMotorClient"
        ) as MockMotor, patch(
            "fastfetchbot_shared.database.mongodb.connection.init_beanie",
            new_callable=AsyncMock,
        ) as mock_init_beanie:
            mock_client = MagicMock()
            mock_db = MagicMock()
            mock_client.__getitem__ = MagicMock(return_value=mock_db)
            MockMotor.return_value = mock_client

            from fastfetchbot_shared.database.mongodb.connection import (
                init_mongodb,
                document_list,
            )

            await init_mongodb("mongodb://localhost:27017", "test_db")

            MockMotor.assert_called_once_with("mongodb://localhost:27017")
            mock_client.__getitem__.assert_called_once_with("test_db")
            mock_init_beanie.assert_awaited_once_with(
                database=mock_db, document_models=document_list
            )

    @pytest.mark.asyncio
    async def test_default_db_name_is_telegram_bot(self):
        with patch(
            "fastfetchbot_shared.database.mongodb.connection.AsyncIOMotorClient"
        ) as MockMotor, patch(
            "fastfetchbot_shared.database.mongodb.connection.init_beanie",
            new_callable=AsyncMock,
        ):
            mock_client = MagicMock()
            mock_client.__getitem__ = MagicMock(return_value=MagicMock())
            MockMotor.return_value = mock_client

            from fastfetchbot_shared.database.mongodb.connection import init_mongodb

            await init_mongodb("mongodb://localhost:27017")

            mock_client.__getitem__.assert_called_once_with("telegram_bot")

    @pytest.mark.asyncio
    async def test_sets_module_level_client(self):
        with patch(
            "fastfetchbot_shared.database.mongodb.connection.AsyncIOMotorClient"
        ) as MockMotor, patch(
            "fastfetchbot_shared.database.mongodb.connection.init_beanie",
            new_callable=AsyncMock,
        ):
            mock_client = MagicMock()
            mock_client.__getitem__ = MagicMock(return_value=MagicMock())
            MockMotor.return_value = mock_client

            from fastfetchbot_shared.database.mongodb import connection
            from fastfetchbot_shared.database.mongodb.connection import init_mongodb

            await init_mongodb("mongodb://localhost:27017")

            assert connection._client is mock_client


# ---------------------------------------------------------------------------
# close_mongodb
# ---------------------------------------------------------------------------


class TestCloseMongodb:
    @pytest.mark.asyncio
    async def test_closes_client_and_sets_to_none(self):
        from fastfetchbot_shared.database.mongodb import connection
        from fastfetchbot_shared.database.mongodb.connection import close_mongodb

        mock_client = MagicMock()
        connection._client = mock_client

        await close_mongodb()

        mock_client.close.assert_called_once()
        assert connection._client is None

    @pytest.mark.asyncio
    async def test_noop_when_client_is_none(self):
        from fastfetchbot_shared.database.mongodb import connection
        from fastfetchbot_shared.database.mongodb.connection import close_mongodb

        connection._client = None

        # Should not raise
        await close_mongodb()
        assert connection._client is None


# ---------------------------------------------------------------------------
# save_instances
# ---------------------------------------------------------------------------


class TestSaveInstances:
    @pytest.mark.asyncio
    async def test_raises_type_error_for_none(self):
        from fastfetchbot_shared.database.mongodb.connection import save_instances

        with pytest.raises(TypeError, match="instances must be a Model"):
            await save_instances(None)

    @pytest.mark.asyncio
    async def test_single_document_calls_insert(self):
        """Test that passing a single Document instance calls type.insert()."""
        from beanie import Document
        from fastfetchbot_shared.database.mongodb.connection import save_instances

        # Create a mock that passes isinstance(x, Document)
        mock_doc = MagicMock(spec=Document)
        mock_doc_type = type(mock_doc)
        mock_doc_type.insert = AsyncMock()

        await save_instances(mock_doc)
        mock_doc_type.insert.assert_awaited_once_with(mock_doc)

    @pytest.mark.asyncio
    async def test_list_of_documents_calls_insert_many(self):
        from fastfetchbot_shared.database.mongodb.connection import save_instances

        mock_doc1 = MagicMock()
        mock_doc2 = MagicMock()
        mock_doc_type = type(mock_doc1)
        mock_doc_type.insert_many = AsyncMock()

        docs = [mock_doc1, mock_doc2]
        await save_instances(docs)
        mock_doc_type.insert_many.assert_awaited_once_with(docs)

    @pytest.mark.asyncio
    async def test_raises_type_error_for_invalid_type(self):
        from fastfetchbot_shared.database.mongodb.connection import save_instances

        with pytest.raises(TypeError, match="instances must be a Model"):
            await save_instances("not_a_document")

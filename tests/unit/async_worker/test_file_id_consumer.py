"""Tests for apps/async-worker/async_worker/services/file_id_consumer.py"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset module-level global state before each test."""
    from async_worker.services import file_id_consumer as fic

    fic._redis = None
    fic._consumer_task = None
    yield
    fic._redis = None
    fic._consumer_task = None


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.brpop = AsyncMock()
    r.lpush = AsyncMock()
    r.aclose = AsyncMock()
    return r


def _make_payload(metadata_url="https://example.com/post/1", file_id_updates=None):
    """Create a JSON-encoded file_id update payload."""
    if file_id_updates is None:
        file_id_updates = [
            {
                "url": "https://img.com/1.jpg",
                "media_type": "image",
                "telegram_file_id": "AgACAgI123",
            },
        ]
    return json.dumps(
        {
            "metadata_url": metadata_url,
            "file_id_updates": file_id_updates,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# _get_redis
# ---------------------------------------------------------------------------


class TestGetRedis:
    @pytest.mark.asyncio
    async def test_creates_connection(self, mock_redis):
        with patch(
            "async_worker.services.file_id_consumer.aioredis.from_url",
            return_value=mock_redis,
        ):
            from async_worker.services.file_id_consumer import _get_redis

            r = await _get_redis()
            assert r is mock_redis

    @pytest.mark.asyncio
    async def test_reuses_connection(self, mock_redis):
        with patch(
            "async_worker.services.file_id_consumer.aioredis.from_url",
            return_value=mock_redis,
        ) as mock_from_url:
            from async_worker.services.file_id_consumer import _get_redis

            r1 = await _get_redis()
            r2 = await _get_redis()
            assert r1 is r2
            mock_from_url.assert_called_once()


# ---------------------------------------------------------------------------
# _process_file_id_update
# ---------------------------------------------------------------------------


class TestProcessFileIdUpdate:
    @pytest.mark.asyncio
    async def test_updates_matching_media_file(self):
        from async_worker.services.file_id_consumer import _process_file_id_update

        # Create a mock Metadata document with media_files
        mock_mf = MagicMock()
        mock_mf.url = "https://img.com/1.jpg"
        mock_mf.telegram_file_id = None

        mock_doc = MagicMock()
        mock_doc.media_files = [mock_mf]
        mock_doc.save = AsyncMock()

        mock_query = MagicMock()
        mock_query.sort = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.first_or_none = AsyncMock(return_value=mock_doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.Metadata"
        ) as MockMetadata:
            MockMetadata.find = MagicMock(return_value=mock_query)
            MockMetadata.url = "url"

            await _process_file_id_update({
                "metadata_url": "https://example.com/post/1",
                "file_id_updates": [
                    {
                        "url": "https://img.com/1.jpg",
                        "media_type": "image",
                        "telegram_file_id": "AgACAgI123",
                    },
                ],
            })

        assert mock_mf.telegram_file_id == "AgACAgI123"
        mock_doc.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_already_set_file_id(self):
        from async_worker.services.file_id_consumer import _process_file_id_update

        mock_mf = MagicMock()
        mock_mf.url = "https://img.com/1.jpg"
        mock_mf.telegram_file_id = "existing_id"  # already set

        mock_doc = MagicMock()
        mock_doc.media_files = [mock_mf]
        mock_doc.save = AsyncMock()

        mock_query = MagicMock()
        mock_query.sort = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.first_or_none = AsyncMock(return_value=mock_doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.Metadata"
        ) as MockMetadata:
            MockMetadata.find = MagicMock(return_value=mock_query)
            MockMetadata.url = "url"

            await _process_file_id_update({
                "metadata_url": "https://example.com/post/1",
                "file_id_updates": [
                    {
                        "url": "https://img.com/1.jpg",
                        "media_type": "image",
                        "telegram_file_id": "new_id",
                    },
                ],
            })

        # Should not overwrite existing file_id
        assert mock_mf.telegram_file_id == "existing_id"
        # No changes → should not save
        mock_doc.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_save_when_no_match(self):
        from async_worker.services.file_id_consumer import _process_file_id_update

        mock_mf = MagicMock()
        mock_mf.url = "https://other.com/2.jpg"  # different URL
        mock_mf.telegram_file_id = None

        mock_doc = MagicMock()
        mock_doc.media_files = [mock_mf]
        mock_doc.save = AsyncMock()

        mock_query = MagicMock()
        mock_query.sort = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.first_or_none = AsyncMock(return_value=mock_doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.Metadata"
        ) as MockMetadata:
            MockMetadata.find = MagicMock(return_value=mock_query)
            MockMetadata.url = "url"

            await _process_file_id_update({
                "metadata_url": "https://example.com/post/1",
                "file_id_updates": [
                    {
                        "url": "https://img.com/1.jpg",
                        "media_type": "image",
                        "telegram_file_id": "AgACAgI123",
                    },
                ],
            })

        mock_doc.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_no_document_found(self):
        from async_worker.services.file_id_consumer import _process_file_id_update

        mock_query = MagicMock()
        mock_query.sort = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.first_or_none = AsyncMock(return_value=None)

        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.Metadata"
        ) as MockMetadata:
            MockMetadata.find = MagicMock(return_value=mock_query)
            MockMetadata.url = "url"

            # Should not raise
            await _process_file_id_update({
                "metadata_url": "https://example.com/missing",
                "file_id_updates": [
                    {
                        "url": "https://img.com/1.jpg",
                        "media_type": "image",
                        "telegram_file_id": "AgACAgI123",
                    },
                ],
            })

    @pytest.mark.asyncio
    async def test_handles_empty_payload(self):
        from async_worker.services.file_id_consumer import _process_file_id_update

        # Should not raise with empty/missing fields
        await _process_file_id_update({"metadata_url": "", "file_id_updates": []})
        await _process_file_id_update({})

    @pytest.mark.asyncio
    async def test_updates_multiple_media_files(self):
        from async_worker.services.file_id_consumer import _process_file_id_update

        mock_mf1 = MagicMock()
        mock_mf1.url = "https://img.com/1.jpg"
        mock_mf1.telegram_file_id = None

        mock_mf2 = MagicMock()
        mock_mf2.url = "https://vid.com/v.mp4"
        mock_mf2.telegram_file_id = None

        mock_doc = MagicMock()
        mock_doc.media_files = [mock_mf1, mock_mf2]
        mock_doc.save = AsyncMock()

        mock_query = MagicMock()
        mock_query.sort = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.first_or_none = AsyncMock(return_value=mock_doc)

        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.Metadata"
        ) as MockMetadata:
            MockMetadata.find = MagicMock(return_value=mock_query)
            MockMetadata.url = "url"

            await _process_file_id_update({
                "metadata_url": "https://example.com/post/1",
                "file_id_updates": [
                    {
                        "url": "https://img.com/1.jpg",
                        "media_type": "image",
                        "telegram_file_id": "photo_id",
                    },
                    {
                        "url": "https://vid.com/v.mp4",
                        "media_type": "video",
                        "telegram_file_id": "video_id",
                    },
                ],
            })

        assert mock_mf1.telegram_file_id == "photo_id"
        assert mock_mf2.telegram_file_id == "video_id"
        mock_doc.save.assert_awaited_once()


# ---------------------------------------------------------------------------
# _consume_loop
# ---------------------------------------------------------------------------


class TestConsumeLoop:
    @pytest.mark.asyncio
    async def test_processes_valid_payload(self, mock_redis):
        payload = _make_payload()
        call_count = 0

        async def brpop_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("fileid:updates", payload)
            raise asyncio.CancelledError()

        mock_redis.brpop = AsyncMock(side_effect=brpop_side_effect)

        with patch(
            "async_worker.services.file_id_consumer.aioredis.from_url",
            return_value=mock_redis,
        ), patch(
            "async_worker.services.file_id_consumer._process_file_id_update",
            new_callable=AsyncMock,
        ) as mock_process:
            from async_worker.services.file_id_consumer import _consume_loop

            await _consume_loop()

            mock_process.assert_awaited_once()
            call_args = mock_process.call_args[0][0]
            assert call_args["metadata_url"] == "https://example.com/post/1"

    @pytest.mark.asyncio
    async def test_brpop_none_continues(self, mock_redis):
        call_count = 0

        async def brpop_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return None
            raise asyncio.CancelledError()

        mock_redis.brpop = AsyncMock(side_effect=brpop_side_effect)

        with patch(
            "async_worker.services.file_id_consumer.aioredis.from_url",
            return_value=mock_redis,
        ):
            from async_worker.services.file_id_consumer import _consume_loop

            await _consume_loop()

        assert call_count == 3


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_task(self, mock_redis):
        from async_worker.services import file_id_consumer as fic

        with patch.object(
            fic, "_consume_loop", new_callable=AsyncMock,
        ):
            await fic.start()
            assert fic._consumer_task is not None
            await fic.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        from async_worker.services import file_id_consumer as fic

        fake_task = MagicMock()
        fic._consumer_task = fake_task

        await fic.start()
        assert fic._consumer_task is fake_task
        fic._consumer_task = None

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, mock_redis):
        from async_worker.services import file_id_consumer as fic

        async def _noop():
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(_noop())
        fic._consumer_task = task
        fic._redis = mock_redis

        await fic.stop()

        assert task.cancelled() or task.done()
        mock_redis.aclose.assert_awaited_once()
        assert fic._consumer_task is None
        assert fic._redis is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        from async_worker.services import file_id_consumer as fic

        fic._consumer_task = None
        fic._redis = None
        await fic.stop()  # should not raise

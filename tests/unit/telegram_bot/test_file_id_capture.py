"""Tests for apps/telegram-bot/core/services/file_id_capture.py"""

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
    import core.services.file_id_capture as fic

    fic._redis = None
    yield
    fic._redis = None


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.lpush = AsyncMock()
    r.aclose = AsyncMock()
    return r


# ---------------------------------------------------------------------------
# extract_file_id
# ---------------------------------------------------------------------------


class TestExtractFileId:
    def test_extracts_photo_file_id(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        photo_small = MagicMock(file_id="small_id")
        photo_large = MagicMock(file_id="large_id")
        msg.photo = [photo_small, photo_large]

        result = extract_file_id(msg, "image")
        assert result == "large_id"  # last = largest

    def test_extracts_video_file_id(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        msg.video = MagicMock(file_id="vid_id")

        result = extract_file_id(msg, "video")
        assert result == "vid_id"

    def test_extracts_animation_file_id(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        msg.animation = MagicMock(file_id="gif_id")

        result = extract_file_id(msg, "gif")
        assert result == "gif_id"

    def test_extracts_audio_file_id(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        msg.audio = MagicMock(file_id="audio_id")

        result = extract_file_id(msg, "audio")
        assert result == "audio_id"

    def test_extracts_document_file_id(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        msg.document = MagicMock(file_id="doc_id")

        result = extract_file_id(msg, "document")
        assert result == "doc_id"

    def test_returns_none_for_empty_photo(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        msg.photo = []

        result = extract_file_id(msg, "image")
        assert result is None

    def test_returns_none_for_missing_video(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        msg.video = None

        result = extract_file_id(msg, "video")
        assert result is None

    def test_returns_none_for_unknown_type(self):
        from core.services.file_id_capture import extract_file_id

        msg = MagicMock()
        result = extract_file_id(msg, "unknown_type")
        assert result is None


# ---------------------------------------------------------------------------
# _get_redis
# ---------------------------------------------------------------------------


class TestGetRedis:
    @pytest.mark.asyncio
    async def test_creates_connection(self, mock_redis):
        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            from core.services.file_id_capture import _get_redis

            r = await _get_redis()
            assert r is mock_redis

    @pytest.mark.asyncio
    async def test_reuses_connection(self, mock_redis):
        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ) as mock_from_url:
            from core.services.file_id_capture import _get_redis

            r1 = await _get_redis()
            r2 = await _get_redis()
            assert r1 is r2
            mock_from_url.assert_called_once()


# ---------------------------------------------------------------------------
# capture_and_push_file_ids
# ---------------------------------------------------------------------------


class TestCaptureAndPushFileIds:
    @pytest.mark.asyncio
    async def test_pushes_file_id_updates(self, mock_redis):
        from core.services.file_id_capture import capture_and_push_file_ids

        # Create mock sent messages
        msg1 = MagicMock()
        photo = MagicMock(file_id="AgACAgI123")
        msg1.photo = [photo]

        msg2 = MagicMock()
        msg2.video = MagicMock(file_id="BAACAgI456")

        uncached_info = [
            {"url": "https://img.com/1.jpg", "media_type": "image"},
            {"url": "https://vid.com/v.mp4", "media_type": "video"},
        ]

        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            await capture_and_push_file_ids(
                uncached_info=uncached_info,
                sent_messages=(msg1, msg2),
                metadata_url="https://example.com/post/1",
            )

        mock_redis.lpush.assert_awaited_once()
        queue_key = mock_redis.lpush.call_args[0][0]
        payload = json.loads(mock_redis.lpush.call_args[0][1])

        assert queue_key == "fileid:updates"
        assert payload["metadata_url"] == "https://example.com/post/1"
        assert len(payload["file_id_updates"]) == 2
        assert payload["file_id_updates"][0]["telegram_file_id"] == "AgACAgI123"
        assert payload["file_id_updates"][1]["telegram_file_id"] == "BAACAgI456"

    @pytest.mark.asyncio
    async def test_skips_none_entries(self, mock_redis):
        """None entries in uncached_info are cached items — skip them."""
        from core.services.file_id_capture import capture_and_push_file_ids

        msg1 = MagicMock()
        msg1.video = MagicMock(file_id="vid_id")

        # First item was cached (None), second was downloaded
        uncached_info = [
            None,
            {"url": "https://vid.com/v.mp4", "media_type": "video"},
        ]

        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            await capture_and_push_file_ids(
                uncached_info=uncached_info,
                sent_messages=(MagicMock(), msg1),
                metadata_url="https://example.com/post/1",
            )

        payload = json.loads(mock_redis.lpush.call_args[0][1])
        assert len(payload["file_id_updates"]) == 1
        assert payload["file_id_updates"][0]["url"] == "https://vid.com/v.mp4"

    @pytest.mark.asyncio
    async def test_no_push_when_all_cached(self, mock_redis):
        """When all items are cached (None), nothing should be pushed."""
        from core.services.file_id_capture import capture_and_push_file_ids

        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            await capture_and_push_file_ids(
                uncached_info=[None, None],
                sent_messages=(MagicMock(), MagicMock()),
                metadata_url="https://example.com/post/1",
            )

        mock_redis.lpush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_push_when_empty_uncached(self, mock_redis):
        from core.services.file_id_capture import capture_and_push_file_ids

        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            await capture_and_push_file_ids(
                uncached_info=[],
                sent_messages=(),
                metadata_url="https://example.com/post/1",
            )

        mock_redis.lpush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_more_uncached_than_messages(self, mock_redis):
        """If uncached_info has more entries than sent_messages, stop at messages length."""
        from core.services.file_id_capture import capture_and_push_file_ids

        msg1 = MagicMock()
        msg1.photo = [MagicMock(file_id="photo_id")]

        uncached_info = [
            {"url": "https://img.com/1.jpg", "media_type": "image"},
            {"url": "https://img.com/2.jpg", "media_type": "image"},  # no message for this
        ]

        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            await capture_and_push_file_ids(
                uncached_info=uncached_info,
                sent_messages=(msg1,),  # only 1 message
                metadata_url="https://example.com/post/1",
            )

        payload = json.loads(mock_redis.lpush.call_args[0][1])
        assert len(payload["file_id_updates"]) == 1

    @pytest.mark.asyncio
    async def test_skips_unextractable_file_ids(self, mock_redis):
        """If extract_file_id returns None, skip that item."""
        from core.services.file_id_capture import capture_and_push_file_ids

        msg1 = MagicMock()
        msg1.photo = []  # empty photo list → extract returns None
        msg1.video = None
        msg1.animation = None
        msg1.audio = None
        msg1.document = None

        uncached_info = [
            {"url": "https://img.com/1.jpg", "media_type": "image"},
        ]

        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            await capture_and_push_file_ids(
                uncached_info=uncached_info,
                sent_messages=(msg1,),
                metadata_url="https://example.com/post/1",
            )

        # No valid file_ids extracted, so nothing pushed
        mock_redis.lpush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_error_is_caught(self, mock_redis):
        """Redis failures should be caught and logged, not raised."""
        from core.services.file_id_capture import capture_and_push_file_ids

        mock_redis.lpush = AsyncMock(side_effect=ConnectionError("Redis down"))

        msg1 = MagicMock()
        msg1.photo = [MagicMock(file_id="photo_id")]

        uncached_info = [
            {"url": "https://img.com/1.jpg", "media_type": "image"},
        ]

        with patch(
            "core.services.file_id_capture.aioredis.from_url",
            return_value=mock_redis,
        ):
            # Should not raise
            await capture_and_push_file_ids(
                uncached_info=uncached_info,
                sent_messages=(msg1,),
                metadata_url="https://example.com/post/1",
            )

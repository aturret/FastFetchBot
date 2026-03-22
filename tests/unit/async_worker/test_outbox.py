"""Tests for apps/async-worker/async_worker/services/outbox.py"""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_outbox_module():
    """Reset module-level global state before each test."""
    import async_worker.services.outbox as outbox_mod

    outbox_mod._redis = None
    yield
    outbox_mod._redis = None


@pytest.fixture
def mock_redis():
    """Create a mock async Redis instance."""
    r = AsyncMock()
    r.lpush = AsyncMock()
    r.aclose = AsyncMock()
    return r


# ---------------------------------------------------------------------------
# get_outbox_redis
# ---------------------------------------------------------------------------


class TestGetOutboxRedis:
    @pytest.mark.asyncio
    async def test_creates_connection_on_first_call(self, mock_redis):
        with patch(
            "async_worker.services.outbox.aioredis.from_url",
            return_value=mock_redis,
        ) as mock_from_url:
            from async_worker.services.outbox import get_outbox_redis

            r = await get_outbox_redis()
            assert r is mock_redis
            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_same_instance_on_second_call(self, mock_redis):
        with patch(
            "async_worker.services.outbox.aioredis.from_url",
            return_value=mock_redis,
        ) as mock_from_url:
            from async_worker.services.outbox import get_outbox_redis

            r1 = await get_outbox_redis()
            r2 = await get_outbox_redis()
            assert r1 is r2
            assert mock_from_url.call_count == 1


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


class TestPush:
    @pytest.mark.asyncio
    async def test_push_metadata_item(self, mock_redis):
        with patch(
            "async_worker.services.outbox.aioredis.from_url",
            return_value=mock_redis,
        ):
            from async_worker.services.outbox import push

            await push(
                job_id="j1",
                chat_id=12345,
                metadata_item={"title": "Test", "content": "hi"},
                message_id=99,
            )

        mock_redis.lpush.assert_awaited_once()
        args = mock_redis.lpush.call_args
        queue_key = args[0][0]
        payload = json.loads(args[0][1])

        assert payload["job_id"] == "j1"
        assert payload["chat_id"] == 12345
        assert payload["message_id"] == 99
        assert payload["metadata_item"] == {"title": "Test", "content": "hi"}
        assert payload["error"] is None

    @pytest.mark.asyncio
    async def test_push_error(self, mock_redis):
        with patch(
            "async_worker.services.outbox.aioredis.from_url",
            return_value=mock_redis,
        ):
            from async_worker.services.outbox import push

            await push(
                job_id="j2",
                chat_id=42,
                error="something broke",
            )

        payload = json.loads(mock_redis.lpush.call_args[0][1])
        assert payload["error"] == "something broke"
        assert payload["metadata_item"] is None

    @pytest.mark.asyncio
    async def test_push_unicode_content(self, mock_redis):
        with patch(
            "async_worker.services.outbox.aioredis.from_url",
            return_value=mock_redis,
        ):
            from async_worker.services.outbox import push

            await push(
                job_id="j3",
                chat_id=1,
                metadata_item={"title": "\u4e2d\u6587\u6807\u9898", "emoji": "\U0001f600"},
            )

        raw = mock_redis.lpush.call_args[0][1]
        # ensure_ascii=False means unicode should be preserved
        assert "\u4e2d\u6587\u6807\u9898" in raw
        assert "\U0001f600" in raw

    @pytest.mark.asyncio
    async def test_push_without_message_id(self, mock_redis):
        with patch(
            "async_worker.services.outbox.aioredis.from_url",
            return_value=mock_redis,
        ):
            from async_worker.services.outbox import push

            await push(job_id="j4", chat_id=1)

        payload = json.loads(mock_redis.lpush.call_args[0][1])
        assert payload["message_id"] is None


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_when_connected(self, mock_redis):
        import async_worker.services.outbox as outbox_mod

        outbox_mod._redis = mock_redis
        await outbox_mod.close()

        mock_redis.aclose.assert_awaited_once()
        assert outbox_mod._redis is None

    @pytest.mark.asyncio
    async def test_close_when_not_connected(self):
        import async_worker.services.outbox as outbox_mod

        outbox_mod._redis = None
        # Should not raise
        await outbox_mod.close()
        assert outbox_mod._redis is None

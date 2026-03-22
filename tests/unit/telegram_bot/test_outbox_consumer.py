"""Tests for apps/telegram-bot/core/services/outbox_consumer.py"""

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
    import core.services.outbox_consumer as oc

    oc._redis = None
    oc._consumer_task = None
    yield
    oc._redis = None
    oc._consumer_task = None


@pytest.fixture
def mock_redis():
    """Create a mock async Redis instance."""
    r = AsyncMock()
    r.brpop = AsyncMock()
    r.aclose = AsyncMock()
    return r


def _make_payload(
    job_id="j1",
    chat_id=42,
    metadata_item=None,
    message_id=None,
    error=None,
):
    """Create a JSON-encoded outbox payload."""
    return json.dumps(
        {
            "job_id": job_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "metadata_item": metadata_item,
            "error": error,
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
            "core.services.outbox_consumer.aioredis.from_url",
            return_value=mock_redis,
        ):
            from core.services.outbox_consumer import _get_redis

            r = await _get_redis()
            assert r is mock_redis

    @pytest.mark.asyncio
    async def test_reuses_connection(self, mock_redis):
        with patch(
            "core.services.outbox_consumer.aioredis.from_url",
            return_value=mock_redis,
        ) as mock_from_url:
            from core.services.outbox_consumer import _get_redis

            r1 = await _get_redis()
            r2 = await _get_redis()
            assert r1 is r2
            mock_from_url.assert_called_once()


# ---------------------------------------------------------------------------
# _consume_loop — success item delivery
# ---------------------------------------------------------------------------


class TestConsumeLoopSuccessItem:
    @pytest.mark.asyncio
    async def test_delivers_metadata_item(self, mock_redis):
        payload = _make_payload(
            metadata_item={"title": "Test", "content": "hi"},
            chat_id=42,
        )
        call_count = 0

        async def brpop_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("scrape:outbox", payload)
            # CancelledError is caught inside _consume_loop and breaks the loop
            raise asyncio.CancelledError()

        mock_redis.brpop = AsyncMock(side_effect=brpop_side_effect)

        with patch(
            "core.services.outbox_consumer.aioredis.from_url",
            return_value=mock_redis,
        ), patch(
            "core.services.outbox_consumer.send_item_message",
            new_callable=AsyncMock,
        ) as mock_send:
            from core.services.outbox_consumer import _consume_loop

            # _consume_loop catches CancelledError and exits cleanly
            await _consume_loop()

            mock_send.assert_awaited_once()
            call_kwargs = mock_send.call_args.kwargs
            assert call_kwargs["chat_id"] == 42


# ---------------------------------------------------------------------------
# _consume_loop — error delivery
# ---------------------------------------------------------------------------


class TestConsumeLoopError:
    @pytest.mark.asyncio
    async def test_sends_error_to_chat(self, mock_redis):
        payload = _make_payload(error="scraper failed", chat_id=99)
        call_count = 0

        async def brpop_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("scrape:outbox", payload)
            raise asyncio.CancelledError()

        mock_redis.brpop = AsyncMock(side_effect=brpop_side_effect)

        with patch(
            "core.services.outbox_consumer.aioredis.from_url",
            return_value=mock_redis,
        ), patch(
            "core.services.outbox_consumer._send_error_to_chat",
            new_callable=AsyncMock,
        ) as mock_err:
            from core.services.outbox_consumer import _consume_loop

            await _consume_loop()

            mock_err.assert_awaited_once_with(99, "scraper failed")


# ---------------------------------------------------------------------------
# _consume_loop — edge cases
# ---------------------------------------------------------------------------


class TestConsumeLoopEdgeCases:
    @pytest.mark.asyncio
    async def test_skips_payload_missing_metadata_and_chat(self, mock_redis):
        payload = _make_payload(metadata_item=None, chat_id=None)
        call_count = 0

        async def brpop_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ("scrape:outbox", payload)
            raise asyncio.CancelledError()

        mock_redis.brpop = AsyncMock(side_effect=brpop_side_effect)

        with patch(
            "core.services.outbox_consumer.aioredis.from_url",
            return_value=mock_redis,
        ), patch(
            "core.services.outbox_consumer.send_item_message",
            new_callable=AsyncMock,
        ) as mock_send:
            from core.services.outbox_consumer import _consume_loop

            await _consume_loop()

            # Should not call send_item_message due to missing metadata/chat
            mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_brpop_none_continues_loop(self, mock_redis):
        """When BRPOP returns None (timeout), loop should continue."""
        call_count = 0

        async def brpop_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return None
            raise asyncio.CancelledError()

        mock_redis.brpop = AsyncMock(side_effect=brpop_side_effect)

        with patch(
            "core.services.outbox_consumer.aioredis.from_url",
            return_value=mock_redis,
        ):
            from core.services.outbox_consumer import _consume_loop

            await _consume_loop()

        assert call_count == 3  # 2 None returns, then cancel


# ---------------------------------------------------------------------------
# _send_error_to_chat
# ---------------------------------------------------------------------------


class TestSendErrorToChat:
    @pytest.mark.asyncio
    async def test_sends_error_message(self):
        mock_bot = AsyncMock()
        mock_app = MagicMock()
        mock_app.bot = mock_bot

        # _send_error_to_chat uses: from core.services.bot_app import application
        with patch("core.services.bot_app.application", mock_app):
            from core.services.outbox_consumer import _send_error_to_chat

            await _send_error_to_chat(42, "something went wrong")

        mock_bot.send_message.assert_awaited_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == 42
        assert "something went wrong" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_handles_send_failure_gracefully(self):
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))
        mock_app = MagicMock()
        mock_app.bot = mock_bot

        with patch("core.services.bot_app.application", mock_app):
            from core.services.outbox_consumer import _send_error_to_chat

            # Should not raise
            await _send_error_to_chat(42, "error")


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_task(self, mock_redis):
        with patch(
            "core.services.outbox_consumer.aioredis.from_url",
            return_value=mock_redis,
        ):
            import core.services.outbox_consumer as oc

            # Make consume_loop exit immediately
            with patch.object(
                oc,
                "_consume_loop",
                new_callable=AsyncMock,
            ):
                await oc.start()
                assert oc._consumer_task is not None

                # Clean up
                await oc.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, mock_redis):
        import core.services.outbox_consumer as oc

        # Set a fake task to simulate "already running"
        fake_task = MagicMock()
        oc._consumer_task = fake_task

        await oc.start()
        # Should still be the original fake task
        assert oc._consumer_task is fake_task

        # Reset to avoid teardown issues
        oc._consumer_task = None

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, mock_redis):
        import core.services.outbox_consumer as oc

        # Create a real asyncio task that we can cancel
        async def _noop():
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(_noop())
        oc._consumer_task = task
        oc._redis = mock_redis

        await oc.stop()

        assert task.cancelled() or task.done()
        mock_redis.aclose.assert_awaited_once()
        assert oc._consumer_task is None
        assert oc._redis is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        import core.services.outbox_consumer as oc

        oc._consumer_task = None
        oc._redis = None
        # Should not raise
        await oc.stop()

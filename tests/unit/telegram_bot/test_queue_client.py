"""Tests for apps/telegram-bot/core/queue_client.py"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset module-level global state before each test."""
    import core.queue_client as qc

    qc._arq_redis = None
    qc._bot_id = None
    yield
    qc._arq_redis = None
    qc._bot_id = None


@pytest.fixture
def mock_arq_pool():
    """Create a mock ARQ Redis pool."""
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    pool.aclose = AsyncMock()
    return pool


# ---------------------------------------------------------------------------
# _parse_redis_url
# ---------------------------------------------------------------------------


class TestParseRedisUrl:
    def test_standard_url(self):
        from core.queue_client import _parse_redis_url

        settings = _parse_redis_url("redis://localhost:6379/2")
        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.database == 2

    def test_url_with_password(self):
        from core.queue_client import _parse_redis_url

        settings = _parse_redis_url("redis://:mypass@redis:6380/3")
        assert settings.host == "redis"
        assert settings.port == 6380
        assert settings.database == 3
        assert settings.password == "mypass"

    def test_no_db_defaults_to_zero(self):
        from core.queue_client import _parse_redis_url

        settings = _parse_redis_url("redis://localhost:6379")
        assert settings.database == 0


# ---------------------------------------------------------------------------
# init / close
# ---------------------------------------------------------------------------


class TestInitClose:
    @pytest.mark.asyncio
    async def test_init_creates_pool(self, mock_arq_pool):
        with patch(
            "core.queue_client.create_pool",
            new_callable=AsyncMock,
            return_value=mock_arq_pool,
        ):
            import core.queue_client as qc

            await qc.init(bot_id=123)
            assert qc._arq_redis is mock_arq_pool
            assert qc._bot_id == 123

    @pytest.mark.asyncio
    async def test_init_idempotent(self, mock_arq_pool):
        with patch(
            "core.queue_client.create_pool",
            new_callable=AsyncMock,
            return_value=mock_arq_pool,
        ) as mock_create:
            import core.queue_client as qc

            await qc.init(bot_id=123)
            await qc.init(bot_id=456)
            mock_create.assert_awaited_once()
            # Should keep the first bot_id
            assert qc._bot_id == 123

    @pytest.mark.asyncio
    async def test_close_closes_pool(self, mock_arq_pool):
        import core.queue_client as qc

        qc._arq_redis = mock_arq_pool
        await qc.close()

        mock_arq_pool.aclose.assert_awaited_once()
        assert qc._arq_redis is None
        assert qc._bot_id is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        import core.queue_client as qc

        qc._arq_redis = None
        # Should not raise
        await qc.close()
        assert qc._arq_redis is None


# ---------------------------------------------------------------------------
# enqueue_scrape
# ---------------------------------------------------------------------------


class TestEnqueueScrape:
    @pytest.mark.asyncio
    async def test_raises_when_not_initialized(self):
        import core.queue_client as qc

        qc._arq_redis = None
        qc._bot_id = None
        with pytest.raises(RuntimeError, match="not initialized"):
            await qc.enqueue_scrape(url="https://example.com", chat_id=1)

    @pytest.mark.asyncio
    async def test_raises_when_bot_id_not_set(self, mock_arq_pool):
        import core.queue_client as qc

        qc._arq_redis = mock_arq_pool
        qc._bot_id = None
        with pytest.raises(RuntimeError, match="not initialized"):
            await qc.enqueue_scrape(url="https://example.com", chat_id=1)

    @pytest.mark.asyncio
    async def test_returns_uuid_job_id(self, mock_arq_pool):
        import core.queue_client as qc

        qc._arq_redis = mock_arq_pool
        qc._bot_id = 123
        job_id = await qc.enqueue_scrape(url="https://example.com", chat_id=42)

        # Should be a valid UUID
        uuid.UUID(job_id)

    @pytest.mark.asyncio
    async def test_enqueues_with_correct_args(self, mock_arq_pool):
        import core.queue_client as qc

        qc._arq_redis = mock_arq_pool
        qc._bot_id = 123
        job_id = await qc.enqueue_scrape(
            url="https://twitter.com/post/1",
            chat_id=42,
            message_id=99,
            source="twitter",
            content_type="social_media",
        )

        mock_arq_pool.enqueue_job.assert_awaited_once()
        call_args = mock_arq_pool.enqueue_job.call_args
        assert call_args.args[0] == "scrape_and_enrich"
        assert call_args.kwargs["url"] == "https://twitter.com/post/1"
        assert call_args.kwargs["chat_id"] == 42
        assert call_args.kwargs["job_id"] == job_id
        assert call_args.kwargs["message_id"] == 99
        assert call_args.kwargs["source"] == "twitter"
        assert call_args.kwargs["content_type"] == "social_media"
        assert call_args.kwargs["bot_id"] == 123

    @pytest.mark.asyncio
    async def test_passes_extra_kwargs(self, mock_arq_pool):
        import core.queue_client as qc

        qc._arq_redis = mock_arq_pool
        qc._bot_id = 123
        await qc.enqueue_scrape(
            url="u", chat_id=1, store_telegraph=True, store_document=False
        )

        call_kwargs = mock_arq_pool.enqueue_job.call_args.kwargs
        assert call_kwargs["store_telegraph"] is True
        assert call_kwargs["store_document"] is False
        assert call_kwargs["bot_id"] == 123

    @pytest.mark.asyncio
    async def test_minimal_args(self, mock_arq_pool):
        import core.queue_client as qc

        qc._arq_redis = mock_arq_pool
        qc._bot_id = 456
        job_id = await qc.enqueue_scrape(url="https://example.com", chat_id=1)

        call_kwargs = mock_arq_pool.enqueue_job.call_args.kwargs
        assert call_kwargs["source"] == ""
        assert call_kwargs["content_type"] == ""
        assert call_kwargs["message_id"] is None
        assert call_kwargs["bot_id"] == 456

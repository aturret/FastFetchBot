"""Tests for apps/async-worker/async_worker/main.py — parse_redis_url and WorkerSettings."""

import pytest

from async_worker.main import parse_redis_url


# ---------------------------------------------------------------------------
# parse_redis_url
# ---------------------------------------------------------------------------


class TestParseRedisUrl:
    def test_default_url(self):
        settings = parse_redis_url("redis://localhost:6379/0")
        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.database == 0
        assert settings.password is None

    def test_custom_db(self):
        settings = parse_redis_url("redis://localhost:6379/2")
        assert settings.database == 2

    def test_custom_host_and_port(self):
        settings = parse_redis_url("redis://myhost:7000/5")
        assert settings.host == "myhost"
        assert settings.port == 7000
        assert settings.database == 5

    def test_with_password(self):
        settings = parse_redis_url("redis://:secret@redis.example.com:6380/3")
        assert settings.host == "redis.example.com"
        assert settings.port == 6380
        assert settings.database == 3
        assert settings.password == "secret"

    def test_no_path_defaults_to_db_0(self):
        settings = parse_redis_url("redis://localhost:6379")
        assert settings.database == 0

    def test_empty_path_defaults_to_db_0(self):
        settings = parse_redis_url("redis://localhost:6379/")
        assert settings.database == 0

    def test_no_port_defaults_to_6379(self):
        settings = parse_redis_url("redis://myhost/1")
        assert settings.port == 6379
        assert settings.database == 1


# ---------------------------------------------------------------------------
# WorkerSettings
# ---------------------------------------------------------------------------


class TestWorkerSettings:
    def test_worker_settings_attributes(self):
        from async_worker.main import WorkerSettings

        assert WorkerSettings.job_timeout == 600
        assert WorkerSettings.max_jobs == 10
        assert WorkerSettings.keep_result == 3600

    def test_worker_settings_has_scrape_function(self):
        from async_worker.main import WorkerSettings
        from async_worker.tasks.scrape import scrape_and_enrich

        assert scrape_and_enrich in WorkerSettings.functions

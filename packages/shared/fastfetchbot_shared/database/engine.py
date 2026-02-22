import os
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///data/fastfetchbot.db"

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _get_database_url() -> str:
    return os.environ.get("SETTINGS_DATABASE_URL", _DEFAULT_DATABASE_URL)


def _ensure_sqlite_dir(url: str) -> None:
    """Create parent directories for SQLite database files."""
    if not url.startswith("sqlite"):
        return
    # sqlite+aiosqlite:///path/to/db → path/to/db
    # sqlite+aiosqlite:////absolute/path → /absolute/path
    db_path = url.split("///", 1)[-1]
    if db_path:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> AsyncEngine:
    """Return the async engine, creating it lazily on first call."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(_get_database_url(), echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory, creating it lazily on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Initialize database: auto-create tables for SQLite, verify schema for PostgreSQL."""
    from fastfetchbot_shared.database.base import Base

    import fastfetchbot_shared.database.models  # noqa: F401

    database_url = _get_database_url()
    engine = get_engine()

    if database_url.startswith("sqlite"):
        _ensure_sqlite_dir(database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    elif database_url.startswith("postgresql"):
        from sqlalchemy import inspect as sa_inspect

        async with engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: sa_inspect(sync_conn).get_table_names()
            )
        required_tables = set(Base.metadata.tables.keys())
        missing = required_tables - set(table_names)
        if missing:
            from fastfetchbot_shared.utils.logger import logger

            logger.error(
                f"Missing database tables: {missing}. "
                f"Run 'alembic upgrade head' to create them."
            )
            raise SystemExit(1)
    else:
        raise ValueError(f"Unsupported database URL scheme: {database_url}")


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None

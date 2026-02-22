import asyncio
import os
import sys
from pathlib import Path

# Ensure the shared package is importable when running alembic from any directory
_shared_root = Path(__file__).resolve().parent.parent
if str(_shared_root) not in sys.path:
    sys.path.insert(0, str(_shared_root))

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from fastfetchbot_shared.database.base import Base

import fastfetchbot_shared.database.models  # noqa: F401

target_metadata = Base.metadata

_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///data/fastfetchbot.db"


def get_url() -> str:
    return os.environ.get("SETTINGS_DATABASE_URL", _DEFAULT_DATABASE_URL)


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

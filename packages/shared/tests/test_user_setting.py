import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fastfetchbot_shared.database.base import Base
from fastfetchbot_shared.database.models.user_setting import UserSetting


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_user_setting(db_session):
    setting = UserSetting(telegram_user_id=123456789, auto_fetch_in_dm=True)
    db_session.add(setting)
    await db_session.commit()

    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == 123456789)
    )
    fetched = result.scalar_one()
    assert fetched.auto_fetch_in_dm is True
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


@pytest.mark.asyncio
async def test_toggle_user_setting(db_session):
    setting = UserSetting(telegram_user_id=123456789, auto_fetch_in_dm=True)
    db_session.add(setting)
    await db_session.commit()

    setting.auto_fetch_in_dm = False
    await db_session.commit()

    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == 123456789)
    )
    fetched = result.scalar_one()
    assert fetched.auto_fetch_in_dm is False


@pytest.mark.asyncio
async def test_default_auto_fetch_is_true(db_session):
    setting = UserSetting(telegram_user_id=999999)
    db_session.add(setting)
    await db_session.commit()

    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == 999999)
    )
    fetched = result.scalar_one()
    assert fetched.auto_fetch_in_dm is True


@pytest.mark.asyncio
async def test_no_record_returns_none(db_session):
    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == 888888)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_ensure_user_settings_creates_row(db_session):
    """ensure pattern: first call creates row with defaults, second is a no-op."""
    user_id = 777777

    # No row yet
    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == user_id)
    )
    assert result.scalar_one_or_none() is None

    # Simulate ensure: create if missing
    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        db_session.add(UserSetting(telegram_user_id=user_id))
        await db_session.commit()

    # Row exists with defaults
    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == user_id)
    )
    setting = result.scalar_one()
    assert setting.auto_fetch_in_dm is True
    assert setting.created_at is not None

    # Second ensure is a no-op — row unchanged
    original_created_at = setting.created_at
    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        db_session.add(UserSetting(telegram_user_id=user_id))
        await db_session.commit()

    result = await db_session.execute(
        select(UserSetting).where(UserSetting.telegram_user_id == user_id)
    )
    setting = result.scalar_one()
    assert setting.auto_fetch_in_dm is True
    assert setting.created_at == original_created_at

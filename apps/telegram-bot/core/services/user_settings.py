from sqlalchemy import select

from fastfetchbot_shared.database.session import get_session
from fastfetchbot_shared.database.models.user_setting import UserSetting

# In-memory cache of user IDs known to have a settings row.
# Resets on process restart — cheap way to avoid a DB query on every message.
_known_user_ids: set[int] = set()


async def ensure_user_settings(user_id: int) -> None:
    """Create a UserSetting row with defaults if one doesn't exist yet."""
    if user_id in _known_user_ids:
        return
    async with get_session() as session:
        result = await session.execute(
            select(UserSetting).where(UserSetting.telegram_user_id == user_id)
        )
        if result.scalar_one_or_none() is None:
            session.add(UserSetting(telegram_user_id=user_id))
    _known_user_ids.add(user_id)


async def get_auto_fetch_in_dm(user_id: int) -> bool:
    """Return the user's auto_fetch_in_dm preference. Defaults to True."""
    async with get_session() as session:
        result = await session.execute(
            select(UserSetting.auto_fetch_in_dm).where(
                UserSetting.telegram_user_id == user_id
            )
        )
        value = result.scalar_one_or_none()
    return value if value is not None else True


async def toggle_auto_fetch_in_dm(user_id: int) -> bool:
    """Toggle auto_fetch_in_dm for the given user. Returns the new value."""
    async with get_session() as session:
        result = await session.execute(
            select(UserSetting).where(UserSetting.telegram_user_id == user_id)
        )
        user_setting = result.scalar_one_or_none()
        if user_setting is None:
            # Safety fallback — ensure_user_settings should have been called,
            # but handle gracefully.
            user_setting = UserSetting(
                telegram_user_id=user_id, auto_fetch_in_dm=False
            )
            session.add(user_setting)
        else:
            user_setting.auto_fetch_in_dm = not user_setting.auto_fetch_in_dm
        return user_setting.auto_fetch_in_dm


async def get_force_refresh_cache(user_id: int) -> bool:
    """Return the user's force_refresh_cache preference. Defaults to False."""
    async with get_session() as session:
        result = await session.execute(
            select(UserSetting.force_refresh_cache).where(
                UserSetting.telegram_user_id == user_id
            )
        )
        value = result.scalar_one_or_none()
    return value if value is not None else False


async def toggle_force_refresh_cache(user_id: int) -> bool:
    """Toggle force_refresh_cache for the given user. Returns the new value."""
    async with get_session() as session:
        result = await session.execute(
            select(UserSetting).where(UserSetting.telegram_user_id == user_id)
        )
        user_setting = result.scalar_one_or_none()
        if user_setting is None:
            user_setting = UserSetting(
                telegram_user_id=user_id, force_refresh_cache=True
            )
            session.add(user_setting)
        else:
            user_setting.force_refresh_cache = not user_setting.force_refresh_cache
        return user_setting.force_refresh_cache

from fastfetchbot_shared.database.mongodb import (
    init_mongodb,
    close_mongodb,
    save_instances,
)
from src.config import settings


async def startup() -> None:
    await init_mongodb(settings.MONGODB_URL)


async def shutdown() -> None:
    await close_mongodb()

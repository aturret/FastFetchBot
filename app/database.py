from typing import Optional, Union, List

from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine, Model

from app.config import MONGODB_URL

client = AsyncIOMotorClient(MONGODB_URL)
engine = AIOEngine(client=client, database="telegram_bot")


async def startup() -> None:
    pass


async def shutdown() -> None:
    pass


async def get_engine() -> AIOEngine:
    return engine


async def save_instances(instances: Union[Model, List[Model]], *args) -> None:
    if instances is None:
        raise TypeError("instances must be a Model or a list of Model")

    if isinstance(instances, Model):
        await engine.save(instances)
    elif isinstance(instances, list):
        await engine.save_all(instances)
    else:
        raise TypeError("instances must be a Model or a list of Model")

    for arg in args:
        if not isinstance(arg, Model):
            raise TypeError("args must be a Model")
        await engine.save(arg)

from typing import Optional, Union, List

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie, Document, Indexed

from app.config import MONGODB_URL
from app.models.database_model import document_list
from app.utils.logger import logger


async def startup() -> None:
    client = AsyncIOMotorClient(MONGODB_URL)
    await init_beanie(database=client["telegram_bot"], document_models=document_list)


async def shutdown() -> None:
    pass


async def save_instances(instances: Union[Document, List[Document]], *args) -> None:
    if instances is None:
        raise TypeError("instances must be a Model or a list of Model")

    if isinstance(instances, Document):
        instance_type = type(instances)
        await instance_type.insert(instances)
    elif isinstance(instances, list):
        instance_type = type(instances[0])
        await instance_type.insert_many(instances)
    else:
        raise TypeError("instances must be a Model or a list of Model")

    for arg in args:
        if not isinstance(arg, Document):
            raise TypeError("args must be a Model")
        instance_type = type(arg)
        await instance_type.insert_one(arg)

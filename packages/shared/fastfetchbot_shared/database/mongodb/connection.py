from typing import Union, List

from beanie import init_beanie, Document
from pymongo import AsyncMongoClient

from fastfetchbot_shared.database.mongodb.models.metadata import document_list
from fastfetchbot_shared.utils.logger import logger

_client: AsyncMongoClient | None = None


async def init_mongodb(mongodb_url: str, db_name: str = "telegram_bot") -> None:
    global _client
    _client = AsyncMongoClient(mongodb_url)
    await init_beanie(database=_client[db_name], document_models=document_list)
    logger.info(f"MongoDB initialized: {db_name}")


async def close_mongodb() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("MongoDB connection closed")


async def save_instances(instances: Union[Document, List[Document]], *args) -> None:
    if instances is None:
        raise TypeError("instances must be a Model or a list of Model")

    if isinstance(instances, Document):
        instance_type = type(instances)
        await instance_type.insert(instances)
    elif isinstance(instances, list):
        if not instances:
            return
        instance_type = type(instances[0])
        await instance_type.insert_many(instances)
    else:
        raise TypeError("instances must be a Model or a list of Model")

    for arg in args:
        if not isinstance(arg, Document):
            raise TypeError("args must be a Model")
        instance_type = type(arg)
        await instance_type.insert_one(arg)

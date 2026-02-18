import asyncio

from fastapi import APIRouter
from fastapi.requests import Request

from src.config import API_KEY_NAME
from src.services.scrapers.common import InfoExtractService
from fastapi import Security
from src.auth import verify_api_key
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.parse import get_url_metadata

router = APIRouter(prefix="/scraper")


@router.post("/getItem", dependencies=[Security(verify_api_key)])
async def get_item_route(request: Request):
    logger.debug("A scraper getItem request received")
    query_params = dict(request.query_params)
    url = query_params.pop("url")
    ban_list = query_params.pop("ban_list", None)
    logger.debug(f"get_item_route: url: {url}, query_params: {query_params}")
    if API_KEY_NAME in query_params:
        query_params.pop(API_KEY_NAME)
    url_metadata = await get_url_metadata(url, ban_list)
    item = InfoExtractService(url_metadata, **query_params)
    result = await item.get_item()
    logger.debug(f"getItem result: {result}")
    return result


@router.post("/getUrlMetadata", dependencies=[Security(verify_api_key)])
async def get_url_metadata_route(request: Request):
    url = request.query_params.get("url")
    ban_list = request.query_params.get("ban_list")
    url_metadata = await get_url_metadata(url, ban_list)
    return url_metadata.to_dict()

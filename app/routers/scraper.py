from fastapi import APIRouter
from fastapi.requests import Request

from app.config import API_KEY_NAME
from app.services.scrapers.common import InfoExtractService
from fastapi import Security
from app.auth import verify_api_key
from app.utils.parse import get_url_metadata

router = APIRouter(prefix="/scraper")


@router.post("/getItem", dependencies=[Security(verify_api_key)])
async def get_item_route(request: Request):
    query_params = dict(request.query_params)
    url = query_params.pop("url")
    ban_list = query_params.pop("ban_list", None)
    if API_KEY_NAME in query_params:
        query_params.pop(API_KEY_NAME)
    url_metadata = await get_url_metadata(url, ban_list)

    item = InfoExtractService(url_metadata, **query_params)
    result = await item.get_item()
    return result


@router.post("/getUrlMetadata", dependencies=[Security(verify_api_key)])
async def get_url_metadata_route(request: Request):
    url = request.query_params.get("url")
    ban_list = request.query_params.get("ban_list")

    url_metadata = await get_url_metadata(url, ban_list)
    return url_metadata.to_dict()


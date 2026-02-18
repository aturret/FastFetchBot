from fastapi import APIRouter
from fastapi.requests import Request

from src.config import INOREADER_APP_ID, INOREADER_APP_KEY
from src.services.inoreader import Inoreader
from src.services.inoreader.process import (
    get_inoreader_item_async,
    process_inoreader_data,
    default_telegram_channel_id
)
from fastapi import Security
from src.auth import verify_api_key

router = APIRouter(prefix="/inoreader")


async def get_inoreader_webhook_data(data: dict):
    result = data["items"]
    return result


@router.post("/triggerAsync", dependencies=[Security(verify_api_key)])
async def inoreader_trigger_webhook(request: Request):
    if not INOREADER_APP_ID or not INOREADER_APP_KEY:
        return "inoreader app id or key not set"
    params = request.query_params
    await get_inoreader_item_async(trigger=True, params=params)
    return "ok"


@router.post("/webhook", dependencies=[Security(verify_api_key)])
async def inoreader_tag_webhook(request: Request):
    data = await request.json()
    data = await Inoreader.process_items_data(data)
    params = request.query_params
    telegram_channel_id = params.get("channel_id", default_telegram_channel_id)
    await process_inoreader_data(data=data, use_inoreader_content=True, telegram_channel_id=telegram_channel_id)
    return "ok"

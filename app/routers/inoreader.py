import asyncio

from fastapi import APIRouter, BackgroundTasks
from fastapi.requests import Request

from app.config import TELEGRAM_CHANNEL_ID, INOREADER_APP_ID, INOREADER_APP_KEY
from app.models.url_metadata import UrlMetadata
from app.services.telegram_bot import send_item_message
from app.services.common import InfoExtractService
from app.services.inoreader import Inoreader
from fastapi import Security
from app.auth import verify_api_key

router = APIRouter(prefix="/inoreader")
telegram_channel_id = TELEGRAM_CHANNEL_ID[0] if TELEGRAM_CHANNEL_ID else None


def get_inoreader_item(data: dict, trigger: bool = False):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if trigger:
        data = loop.run_until_complete(Inoreader.request_api_info())
    url_metadata = UrlMetadata(
        url=data["aurl"],
        content_type="social_media",
        source="inoreader",
    )
    item = InfoExtractService(url_metadata=url_metadata, data=data, store_document=True)
    metadata_item = loop.run_until_complete(item.get_item())
    loop.run_until_complete(
        send_item_message(metadata_item, chat_id=telegram_channel_id)
    )


async def get_inoreader_item_async(data: dict, trigger: bool = False):
    if trigger:
        data = await Inoreader.request_api_info()
    url_metadata = UrlMetadata(
        url=data["aurl"],
        content_type="social_media",
        source="inoreader",
    )
    item = InfoExtractService(url_metadata=url_metadata, data=data, store_document=True)
    metadata_item = await item.get_item()
    await send_item_message(metadata_item, chat_id=telegram_channel_id)


@router.post("/", dependencies=[Security(verify_api_key)])
async def inoreader_repost_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    background_tasks.add_task(get_inoreader_item, data, False)
    return "ok"


@router.post("/trigger", dependencies=[Security(verify_api_key)])
async def inoreader_trigger_webhook(
        request: Request, background_tasks: BackgroundTasks
):
    if not INOREADER_APP_ID or not INOREADER_APP_KEY:
        return "inoreader app id or key not set"
    background_tasks.add_task(get_inoreader_item, {}, True)
    return "ok"


@router.post("/triggerAsync", dependencies=[Security(verify_api_key)])
async def inoreader_trigger_webhook(
        request: Request
):
    if not INOREADER_APP_ID or not INOREADER_APP_KEY:
        return "inoreader app id or key not set"
    await get_inoreader_item_async({}, True)
    return "ok"


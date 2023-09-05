import asyncio

from fastapi import APIRouter, BackgroundTasks
from fastapi.requests import Request

from app.config import TELEGRAM_CHANNEL_ID
from app.models.url_metadata import UrlMetadata
from app.services.telegram_bot import send_item_message
from app.services.common import InfoExtractService
from fastapi import Security
from app.auth import verify_api_key


router = APIRouter(prefix="/inoreader")
telegram_channel_id = TELEGRAM_CHANNEL_ID[0] if TELEGRAM_CHANNEL_ID else None


def get_inoreader_item(data: dict):
    url_metadata = UrlMetadata(
        url=data["aurl"],
        content_type="social_media",
        source="inoreader",
    )
    item = InfoExtractService(url_metadata=url_metadata, data=data, store_document=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    metadata_item = loop.run_until_complete(item.get_item())
    loop.run_until_complete(
        send_item_message(metadata_item, chat_id=telegram_channel_id)
    )


@router.post("/", dependencies=[Security(verify_api_key)])
async def inoreader_repost_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    background_tasks.add_task(get_inoreader_item, data)
    return "ok"

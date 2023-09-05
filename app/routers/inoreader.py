from fastapi import APIRouter
from fastapi.requests import Request

from app.config import TELEGRAM_CHANNEL_ID
from app.models.url_metadata import UrlMetadata
from app.services.telegram_bot import send_item_message
from app.services.common import InfoExtractService
from fastapi import Security
from app.auth import verify_api_key


router = APIRouter(prefix="/inoreader")
telegram_channel_id = TELEGRAM_CHANNEL_ID[0] if TELEGRAM_CHANNEL_ID else None

@router.post("/", dependencies=[Security(verify_api_key)])
async def inoreader_repost_webhook(request: Request):
    data = await request.json()
    url_metadata = UrlMetadata(
        url=data["aurl"],
        content_type="social_media",
        source="inoreader",
    )
    item = InfoExtractService(url_metadata=url_metadata, data=data, store_document=True)
    metadata_item = await item.get_item()
    await send_item_message(metadata_item,chat_id=telegram_channel_id)
    return "ok"

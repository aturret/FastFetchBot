from fastapi import APIRouter
from fastapi.requests import Request

from app.services.common import InfoExtractService
from app.config import TELEGRAM_WEBHOOK_URL


router = APIRouter(prefix="/inoreader")


@router.post("/")
async def inoreader_repost_webhook(request: Request):
    # TODO: add security check
    data = await request.json()
    url_metadata = {
        "url": data["url"],
        "type": "social_media",
        "source": "inoreader",
    }
    item = InfoExtractService(url_metadata, data)
    await item.get_item()
    return "ok"

from fastapi import APIRouter
from fastapi.requests import Request

from app.services.common import InfoExtractService
from fastapi import Security
from app.auth import verify_api_key


router = APIRouter(prefix="/inoreader")


@router.post("/", dependencies=[Security(verify_api_key)])
async def inoreader_repost_webhook(request: Request):
    data = await request.json()
    url_metadata = {
        "url": data["url"],
        "type": "social_media",
        "source": "inoreader",
    }
    item = InfoExtractService(url_metadata, data)
    await item.get_item()
    return "ok"

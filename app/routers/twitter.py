from fastapi import APIRouter

from app.services.scrapers.common import InfoExtractService
from fastapi import Security
from app.auth import verify_api_key


router = APIRouter(prefix="/twitter")


@router.post("/repost", dependencies=[Security(verify_api_key)])
async def twitter_repost_webhook(url: str):
    url_metadata = {
        "url": url,
        "type": "social_media",
        "source": "twitter",
    }
    item = InfoExtractService(url_metadata)
    await item.get_item()
    return "ok"

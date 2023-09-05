from fastapi import APIRouter
from fastapi.requests import Request

from app.models.url_metadata import UrlMetadata
from app.services.common import InfoExtractService
from fastapi import Security
from app.auth import verify_api_key


router = APIRouter(prefix="/inoreader")


@router.post("/", dependencies=[Security(verify_api_key)])
async def inoreader_repost_webhook(request: Request):
    data = await request.json()
    url_metadata = UrlMetadata(
        url=data["aurl"],
        content_type="social_media",
        source="inoreader",
    )
    item = InfoExtractService(url_metadata=url_metadata, data=data)
    await item.get_item()
    return "ok"

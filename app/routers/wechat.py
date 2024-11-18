from fastapi import APIRouter
from fastapi.requests import Request

from app.models.url_metadata import UrlMetadata
from app.services.scrapers.common import InfoExtractService
from fastapi import Security
from app.auth import verify_api_key

router = APIRouter(prefix="/wechat")


@router.post("/gzh", dependencies=[Security(verify_api_key)])
async def wechat_gzh_scrape(request: Request):
    url = request.query_params.get("url")
    if url:
        url_metadata = UrlMetadata.from_dict({
            "url": url,
            "type": "social_media",
            "source": "wechat",
        })
    else:
        customized_url_metadata = request.json()
        if customized_url_metadata:
            url_metadata = UrlMetadata.from_dict(customized_url_metadata)
        else:
            return "url or url metadata not found"
    item = InfoExtractService(url_metadata)
    result = await item.get_item()
    return result

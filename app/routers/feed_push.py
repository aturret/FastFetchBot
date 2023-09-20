# TODO: this script is now unused, will be removed in the future
import asyncio

from fastapi import APIRouter, BackgroundTasks
from fastapi.requests import Request

from app.config import TELEGRAM_CHANNEL_ID
from app.models.url_metadata import UrlMetadata
from app.services.telegram_bot import send_item_message
from app.services.common import InfoExtractService
from app.services.inoreader import Inoreader
from fastapi import Security
from app.auth import verify_api_key
from app.utils.logger import logger
from app.utils.parse import check_url_type

router = APIRouter(prefix="/feedPush")


async def get_feed_item(url: str, channel_id: str, **kwargs):
    try:
        channel_id = int(channel_id) if channel_id.startswith("-") else channel_id
        url_metadata = await check_url_type(url)
        item = InfoExtractService(url_metadata, **kwargs)
        metadata_item = await item.get_item()
        if channel_id not in TELEGRAM_CHANNEL_ID:
            logger.error(f"channel_id {channel_id} not found")
            return
        await send_item_message(metadata_item, chat_id=channel_id)
    except Exception as e:
        logger.error(f"Error while getting item: {e}")


@router.post("/", dependencies=[Security(verify_api_key)])
async def push_feed_item(
    request: Request,
):
    try:
        data = await request.json()
        params = request.query_params
        url = (
            data.get("url")
            or data.get("aurl")
            or params.get("url")
            or params.get("aurl")
        )
        if not url:
            return f"Error: url is required"
        channel_id = data.get("channelId") or params.get("channelId")
        if not channel_id:
            return f"Error: channelId is required"
        kwargs = data.get("kwargs", {})
        await get_feed_item(url, channel_id, **kwargs)
        return "ok"
    except Exception as e:
        return f"Error: {e}"

import asyncio
from typing import Union, Optional, Dict

from fastapi import APIRouter, BackgroundTasks
from fastapi.requests import Request

from app.config import TELEGRAM_CHANNEL_ID, INOREADER_APP_ID, INOREADER_APP_KEY
from app.models.url_metadata import UrlMetadata
from app.services.telegram_bot import send_item_message
from app.services.common import InfoExtractService
from app.services.inoreader import Inoreader
from fastapi import Security
from app.auth import verify_api_key
from app.utils.logger import logger
from app.utils.parse import check_url_type, get_bool

router = APIRouter(prefix="/inoreader")
default_telegram_channel_id = TELEGRAM_CHANNEL_ID[0] if TELEGRAM_CHANNEL_ID else None


# def get_inoreader_item(
#     data: dict,
#     trigger: bool = False,
#     telegram_channel_id: Union[int, str] = default_telegram_channel_id,
# ):
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     if trigger:
#         data = loop.run_until_complete(Inoreader.request_api_info())
#     url_metadata = UrlMetadata(
#         url=data["aurl"],
#         content_type="social_media",
#         source="inoreader",
#     )
#     item = InfoExtractService(url_metadata=url_metadata, data=data, store_document=True)
#     metadata_item = loop.run_until_complete(item.get_item())
#     loop.run_until_complete(
#         send_item_message(metadata_item, chat_id=telegram_channel_id)
#     )


async def get_inoreader_item_async(
    data: Optional[Dict] = None,
    trigger: bool = False,
    params: Optional[Dict] = None,
    # filters: Optional[Dict] = None,
) -> None:
    stream_id = None
    use_inoreader_content = True
    telegram_channel_id = default_telegram_channel_id
    if trigger and params and not data:
        logger.debug(f"params:{params}")
        use_inoreader_content = get_bool(params.get("useInoreaderContent"), True)
        stream_type = params.get("streamType", "broadcast")
        telegram_channel_id = params.get("channelId", default_telegram_channel_id)
        tag = params.get("tag", None)
        feed = params.get("feed", None)
        the_remaining_params = {
            k: v
            for k, v in params.items()
            if k not in ["streamType", "channelId", "tag", "feed"]
        }
        data = await Inoreader.get_api_item_data(
            stream_type=stream_type, tag=tag, params=the_remaining_params, feed=feed
        )
        if not data:
            return
        stream_id = Inoreader.get_stream_id(stream_type=stream_type, tag=tag, feed=feed)
    if type(data) is dict:
        data = [data]
    await process_inoreader_data(
        data, use_inoreader_content, telegram_channel_id, stream_id
    )
    if stream_id:
        await Inoreader.mark_all_as_read(stream_id=stream_id)


async def process_inoreader_data(
    data: list,
    use_inoreader_content: bool,
    telegram_channel_id: Union[int, str] = default_telegram_channel_id,
    stream_id: str = None,
):
    for item in data:
        url_type_item = await check_url_type(item["aurl"])
        url_type_dict = url_type_item.to_dict()
        logger.debug(f"ino original: {use_inoreader_content}")
        if (
            use_inoreader_content is True
            or url_type_dict["content_type"] == "unknown"
            or url_type_dict["source"] == "zhihu"
        ):
            is_video = url_type_dict["content_type"] == "video"
            content_type = url_type_dict["content_type"] if is_video else "social_media"
            source = url_type_dict["source"] if is_video else "inoreader"
            url_metadata = UrlMetadata(
                url=item["aurl"],
                content_type=content_type,
                source=source,
            )
            metadata_item = InfoExtractService(
                url_metadata=url_metadata,
                data=item,
                store_document=True,
                category=item["category"],
            )
        else:
            metadata_item = InfoExtractService(
                url_metadata=url_type_item,
                data=item,
                store_document=True,
            )
        message_metadata_item = await metadata_item.get_item()
        await send_item_message(message_metadata_item, chat_id=telegram_channel_id)
        if stream_id:
            await Inoreader.mark_all_as_read(
                stream_id=stream_id, timestamp=item["timestamp"]
            )


# @router.post("/", dependencies=[Security(verify_api_key)])
# async def inoreader_repost_webhook(request: Request, background_tasks: BackgroundTasks):
#     data = await request.json()
#     background_tasks.add_task(get_inoreader_item, data, False)
#     return "ok"


# @router.post("/trigger", dependencies=[Security(verify_api_key)])
# async def inoreader_trigger_webhook(
#     request: Request, background_tasks: BackgroundTasks
# ):
#     if not INOREADER_APP_ID or not INOREADER_APP_KEY:
#         return "inoreader app id or key not set"
#     background_tasks.add_task(get_inoreader_item, {}, True)
#     return "ok"


@router.post("/triggerAsync", dependencies=[Security(verify_api_key)])
async def inoreader_trigger_webhook(request: Request):
    if not INOREADER_APP_ID or not INOREADER_APP_KEY:
        return "inoreader app id or key not set"
    params = request.query_params
    await get_inoreader_item_async(trigger=True, params=params)
    return "ok"

from typing import Union, Optional, Dict, Callable, Awaitable

from app.config import TELEGRAM_CHANNEL_ID
from app.models.url_metadata import UrlMetadata
from app.services.inoreader import Inoreader
from app.services.scrapers.common import InfoExtractService
from app.utils.logger import logger
from app.utils.parse import get_url_metadata, get_bool

default_telegram_channel_id = TELEGRAM_CHANNEL_ID[0] if TELEGRAM_CHANNEL_ID else None

# Type alias for the message callback
MessageCallback = Callable[[dict, Union[int, str]], Awaitable[None]]


async def _default_message_callback(metadata_item: dict, chat_id: Union[int, str]) -> None:
    """Default callback that sends via Telegram bot. Used when no callback is provided."""
    from app.services.telegram_bot import send_item_message
    await send_item_message(metadata_item, chat_id=chat_id)


async def process_inoreader_data(
        data: list,
        use_inoreader_content: bool,
        telegram_channel_id: Union[int, str] = default_telegram_channel_id,
        stream_id: str = None,
        message_callback: MessageCallback = None,
):
    if message_callback is None:
        message_callback = _default_message_callback

    for item in data:
        url_type_item = await get_url_metadata(item["aurl"])
        url_type_dict = url_type_item.to_dict()
        logger.debug(f"ino original: {use_inoreader_content}")
        if (
                use_inoreader_content is True
                or url_type_dict["content_type"] == "unknown"
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
        await message_callback(message_metadata_item, telegram_channel_id)
        if stream_id:
            await Inoreader.mark_all_as_read(
                stream_id=stream_id, timestamp=item["timestamp"] - 1
            )


async def get_inoreader_item_async(
        data: Optional[Dict] = None,
        trigger: bool = False,
        params: Optional[Dict] = None,
        message_callback: MessageCallback = None,
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
        data, use_inoreader_content, telegram_channel_id, stream_id,
        message_callback=message_callback,
    )
    if stream_id:
        await Inoreader.mark_all_as_read(stream_id=stream_id)

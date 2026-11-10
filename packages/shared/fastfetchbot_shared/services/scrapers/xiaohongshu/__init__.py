import re
from typing import Any

from fastfetchbot_shared.models.metadata_item import MetadataItem, MediaFile, MessageType
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.parse import (
    unix_timestamp_to_utc,
    get_html_text_length,
    wrap_text_into_html,
)
from fastfetchbot_shared.services.scrapers.config import JINJA2_ENV, XHS_COOKIE_STRING
from .adaptar import XhsSinglePostAdapter

environment = JINJA2_ENV
short_text_template = environment.get_template("xiaohongshu_short_text.jinja2")
content_template = environment.get_template("xiaohongshu_content.jinja2")


class Xiaohongshu(MetadataItem):
    def __init__(self, url: str, data: Any, **kwargs):
        self.url = url
        self.id = None
        self.media_files = []
        self.category = "xiaohongshu"
        self.message_type = MessageType.SHORT
        # auxiliary fields
        self.ip_location = None
        self.share_count = None
        self.comment_count = None
        self.collected_count = None
        self.like_count = None
        self.updated = None
        self.created = None
        self.timestamp = None
        self.raw_content = None

    async def get_item(self) -> dict:
        await self._get_xiaohongshu()
        return self.to_dict()

    async def _get_xiaohongshu(self) -> None:
        async with XhsSinglePostAdapter(cookies=XHS_COOKIE_STRING) as adapter:
            result = await adapter.fetch_post(note_url=self.url)
        note = result["note"]
        self.id = note.get("note_id")
        self.url = result["url"]
        await self._process_xiaohongshu_note(note)

    async def _process_xiaohongshu_note(self, json_data: dict):
        user = json_data.get("user", {}) or {}
        self.title = json_data.get("title")
        self.author = user.get("nickname")
        if not self.title and self.author:
            self.title = f"{self.author}的小红书笔记"
        self.author_url = (
            "https://www.xiaohongshu.com/user/profile/" + user.get("user_id", "")
        )
        self.raw_content = clean_xhs_hashtags(json_data.get("desc", ""))
        raw_time = json_data.get("time", 0)
        raw_updated = json_data.get("last_update_time", 0)
        self.timestamp = _parse_xiaohongshu_timestamp(raw_time)
        updated_timestamp = _parse_xiaohongshu_timestamp(raw_updated)
        self.created = unix_timestamp_to_utc(self.timestamp) if self.timestamp else None
        self.updated = (
            unix_timestamp_to_utc(updated_timestamp) if updated_timestamp else None
        )
        self.like_count = json_data.get("liked_count")
        self.collected_count = json_data.get("collected_count")
        self.comment_count = json_data.get("comment_count")
        self.share_count = json_data.get("share_count")
        self.ip_location = json_data.get("ip_location")
        self.media_files.extend(_build_media_files(json_data))
        data = self.__dict__
        raw_content = self.raw_content or ""
        data["raw_content"] = raw_content.replace("\t", "")
        if data["raw_content"].endswith("\n"):
            data["raw_content"] = data["raw_content"][:-1]
        self.text = short_text_template.render(data=data)
        if get_html_text_length(self.text) > 500:
            self.message_type = MessageType.LONG
        data["raw_content"] = wrap_text_into_html(self.raw_content)
        for media_file in self.media_files:
            if media_file.media_type == "image":
                data["raw_content"] += f'<p><img src="{media_file.url}" alt=""/></p>'
            elif media_file.media_type == "video":
                data["raw_content"] += (
                    f'<p><video src="{media_file.url}" controls="controls"></video></p>'
                )
        self.content = content_template.render(data=data)


def _build_media_files(json_data: dict) -> list[MediaFile]:
    """Turn the adapter's normalized `media` list into MediaFile objects.

    Live photos become two entries: the still image and its motion video.
    Falls back to `image_list` / `video_urls` for payloads without `media`.
    """
    media = json_data.get("media")
    if media is None:
        files = [MediaFile(url=url, media_type="image") for url in json_data.get("image_list", []) or []]
        video_urls = json_data.get("video_urls", []) or []
        if video_urls:
            files.append(MediaFile(url=video_urls[0], media_type="video"))
        return files

    files: list[MediaFile] = []
    for item in media:
        size = {"width": item.get("width") or None, "height": item.get("height") or None}
        if item.get("type") == "video":
            files.append(
                MediaFile(url=item["url"], media_type="video", duration=item.get("duration") or None, **size)
            )
            continue
        files.append(MediaFile(url=item["url"], media_type="image", **size))
        if item.get("type") == "live_photo" and item.get("video_url"):
            files.append(MediaFile(url=item["video_url"], media_type="video", **size))
    return files


_XHS_TOPIC_RE = re.compile(r"#([^#\[\]]+)\[话题\]# ?")


def clean_xhs_hashtags(desc: str | None) -> str:
    """Turn XHS topic markup `#话题[话题]#` into plain `#话题`."""
    if not desc:
        return ""
    # Keep the text before the tag intact; emit exactly one space after it so that
    # adjacent tags (`#a[话题]##b[话题]#`) stay separated.
    return _XHS_TOPIC_RE.sub(lambda m: f"#{m.group(1)} ", desc).strip()


def _parse_xiaohongshu_timestamp(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return timestamp // 1000 if timestamp > 10_000_000_000 else timestamp

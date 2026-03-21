from typing import Any

from fastfetchbot_shared.models.metadata_item import MetadataItem, MediaFile, MessageType
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.parse import (
    unix_timestamp_to_utc,
    get_html_text_length,
    wrap_text_into_html,
)
from fastfetchbot_shared.services.scrapers.config import JINJA2_ENV, XHS_COOKIE_STRING, XHS_SIGN_SERVER_URL
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
        self.raw_content = None

    async def get_item(self) -> dict:
        await self._get_xiaohongshu()
        return self.to_dict()

    async def _get_xiaohongshu(self) -> None:
        async with XhsSinglePostAdapter(
            cookies=XHS_COOKIE_STRING,
            sign_server_endpoint=XHS_SIGN_SERVER_URL,
        ) as adapter:
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
        self.raw_content = json_data.get("desc", "")
        raw_time = json_data.get("time", 0)
        raw_updated = json_data.get("last_update_time", 0)
        self.created = (
            unix_timestamp_to_utc(int(raw_time) / 1000) if raw_time else None
        )
        self.updated = (
            unix_timestamp_to_utc(int(raw_updated) / 1000) if raw_updated else None
        )
        self.like_count = json_data.get("liked_count")
        self.collected_count = json_data.get("collected_count")
        self.comment_count = json_data.get("comment_count")
        self.share_count = json_data.get("share_count")
        self.ip_location = json_data.get("ip_location")
        for image_url in json_data.get("image_list", []) or []:
            self.media_files.append(MediaFile(url=image_url, media_type="image"))
        video_urls = json_data.get("video_urls", []) or []
        if video_urls:
            self.media_files.append(MediaFile(url=video_urls[0], media_type="video"))
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

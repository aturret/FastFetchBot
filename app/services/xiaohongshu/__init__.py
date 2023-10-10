import asyncio
import json
from typing import Dict, Any
from urllib.parse import urlparse

import httpx
import jmespath
from bs4 import BeautifulSoup

from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.utils.config import HEADERS
from app.config import JINJA2_ENV, HTTP_REQUEST_TIMEOUT
from .xhs.core import XiaoHongShuCrawler
from .xhs.client import XHSClient
from .xhs import proxy_account_pool

from ...utils.logger import logger
from ...utils.parse import (
    unix_timestamp_to_utc,
    get_html_text_length,
    wrap_text_into_html,
)

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
        await self.get_xiaohongshu()
        return self.to_dict()

    async def get_xiaohongshu(self) -> None:
        if self.url.find("xiaohongshu.com") == -1:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    self.url,
                    headers=HEADERS,
                    follow_redirects=True,
                    timeout=HTTP_REQUEST_TIMEOUT,
                )
                if (
                    resp.history
                ):  # if there is a redirect, the request will have a response chain
                    for h in resp.history:
                        print(h.status_code, h.url)
                    self.url = str(resp.url)
        urlparser = urlparse(self.url)
        self.id = urlparser.path.split("/")[-1]
        crawler = XiaoHongShuCrawler()
        account_pool = proxy_account_pool.create_account_pool()
        crawler.init_config("xhs", "cookie", account_pool)
        note_detail = None
        for _ in range(30):
            try:
                note_detail = await crawler.start(id=self.id)
                break
            except Exception as e:
                await asyncio.sleep(3)
                logger.error(f"error: {e}")
                logger.error(f"retrying...")
        if not note_detail:
            raise Exception("重试了这么多次还是无法签名成功，寄寄寄")
        # logger.debug(f"json_data: {json.dumps(note_detail, ensure_ascii=False, indent=4)}")
        parsed_data = self.process_note_json(note_detail)
        await self.process_xiaohongshu_note(parsed_data)

    async def process_xiaohongshu_note(self, json_data: dict):
        self.title = json_data.get("title")
        self.author = json_data.get("author")
        self.author_url = "https://www.xiaohongshu.com/user/profile/" + json_data.get(
            "user_id"
        )
        self.raw_content = json_data.get("raw_content")
        logger.debug(f"{json_data.get('created')}")
        self.created = (
            unix_timestamp_to_utc(json_data.get("created") / 1000)
            if json_data.get("created")
            else None
        )
        self.updated = (
            unix_timestamp_to_utc(json_data.get("updated") / 1000)
            if json_data.get("updated")
            else None
        )
        self.like_count = json_data.get("like_count")
        self.collected_count = json_data.get("collected_count")
        self.comment_count = json_data.get("comment_count")
        self.share_count = json_data.get("share_count")
        self.ip_location = json_data.get("ip_location")
        if json_data.get("image_list"):
            for image_url in json_data.get("image_list"):
                self.media_files.append(MediaFile(url=image_url, media_type="image"))
        if json_data.get("video"):
            self.media_files.append(
                MediaFile(url=json_data.get("video"), media_type="video")
            )
        data = self.__dict__
        data["raw_content"] = data["raw_content"].replace("\t", "")
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
                data[
                    "raw_content"
                ] += (
                    f'<p><video src="{media_file.url}" controls="controls"></video></p>'
                )
        self.content = content_template.render(data=data)

    @staticmethod
    def process_note_json(json_data: dict):
        expression = """
        {
        title: title,
        raw_content: desc,
        author: user.nickname,
        user_id: user.user_id,
        image_list: image_list[*].url,
        video: video.media.stream.h264[0].master_url,
        like_count: interact_info.liked_count,
        collected_count: interact_info.collected_count,
        comment_count: interact_info.comment_count,
        share_count: interact_info.share_count,
        ip_location: ip_location,
        created: time,
        updated: last_update_time
        }
        """
        return jmespath.search(expression, json_data)

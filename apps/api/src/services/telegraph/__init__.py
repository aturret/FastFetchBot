# TODO: copy the html-to-telegraph package and modify it to fit the asynchronous model
import random
import traceback
from typing import Any

from html_telegraph_poster_v2.async_poster import (
    AsyncTelegraphPoster,
)
from html_telegraph_poster_v2.async_poster.utils import DocumentPreprocessor

from src.config import TELEGRAPH_TOKEN_LIST
from fastfetchbot_shared.models.telegraph_item import TelegraphItem, from_str
from fastfetchbot_shared.utils.logger import logger


class Telegraph(TelegraphItem):
    def __init__(
        self,
        title: str,
        url: str,
        author: str,
        author_url: str,
        category: str,
        content: str,
    ):
        self.telegraph = AsyncTelegraphPoster(use_api=True)
        self.title = title
        self.url = url
        self.author = author
        self.author_url = author_url
        self.category = category
        self.content = content

    @staticmethod
    def from_dict(obj: Any) -> "Telegraph":
        assert isinstance(obj, dict)
        title = from_str(obj.get("title"))
        url = from_str(obj.get("url"))
        author = from_str(obj.get("author"))
        author_url = from_str(obj.get("author_url"))
        category = from_str(obj.get("category"))
        content = from_str(obj.get("content"))
        return Telegraph(title, url, author, author_url, category, content)

    async def get_telegraph(self, upload_images: bool = True) -> str:
        try:
            if upload_images:
                temp_html = DocumentPreprocessor(self.content, url=self.url)
                logger.info("Telegraph: Uploading images to telegraph...")
                await temp_html.upload_all_images()
                self.content = temp_html.get_processed_html()
            logger.info("Telegraph: Uploading to telegraph...")
            if not TELEGRAPH_TOKEN_LIST:
                await self.telegraph.create_api_token(
                    short_name=self.author[0:14], author_name=self.author
                )
            else:
                random_token = random.choice(TELEGRAPH_TOKEN_LIST)
                await self.telegraph.set_token(random_token)

            telegraph_post = await self.telegraph.post(
                title=self.title,
                author=self.author,
                author_url=self.author_url,
                text=self.content,
            )
            logger.info(
                f"Telegraph: Uploaded to telegraph. Link: {telegraph_post['url']}"
            )
            telegraph_url = telegraph_post["url"]
            return telegraph_url
        except Exception as e:
            traceback.print_exc()
            return ""

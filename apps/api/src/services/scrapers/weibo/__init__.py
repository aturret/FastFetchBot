import json
from dataclasses import dataclass
from typing import Optional, Any
from urllib.parse import urlparse

import httpx
import jmespath
from bs4 import BeautifulSoup
from lxml import html

from fastfetchbot_shared.models.metadata_item import MetadataItem, MediaFile, MessageType
from fastfetchbot_shared.utils.network import get_response_json, get_random_user_agent
from fastfetchbot_shared.utils.parse import get_html_text_length, wrap_text_into_html
from .config import (
    AJAX_HOST,
    AJAX_LONGTEXT_HOST,
    WEIBO_WEB_HOST,
    WEIBO_HOST,
    WEIBO_TEXT_LIMIT,
)
from src.config import JINJA2_ENV, WEIBO_COOKIES
from fastfetchbot_shared.utils.logger import logger

short_text_template = JINJA2_ENV.get_template("weibo_short_text.jinja2")
content_template = JINJA2_ENV.get_template("weibo_content.jinja2")


@dataclass
class Weibo(MetadataItem):
    id: str = ""

    @staticmethod
    def from_dict(obj: Any) -> "Weibo":
        weibo_item = MetadataItem.from_dict(obj)
        weibo_item.id = obj.get("id")
        return Weibo(
            url=weibo_item.url,
            title=weibo_item.title,
            author=weibo_item.author,
            author_url=weibo_item.author_url,
            telegraph_url=weibo_item.telegraph_url,
            text=weibo_item.text,
            content=weibo_item.content,
            media_files=weibo_item.media_files,
            category=weibo_item.category,
            message_type=weibo_item.message_type,
            id=weibo_item.id,
        )

    def to_dict(self) -> dict:
        result: dict = super().to_dict()
        result["id"] = self.id
        return result


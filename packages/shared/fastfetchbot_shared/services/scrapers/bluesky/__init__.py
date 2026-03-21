import traceback
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Dict, Optional, Any

import httpx
import jmespath

from fastfetchbot_shared.models.metadata_item import MetadataItem, MediaFile, MessageType
from fastfetchbot_shared.utils.parse import get_html_text_length, wrap_text_into_html


@dataclass
class Bluesky(MetadataItem):
    cid: str = ""
    author_did: str = ""
    retweet_post: Optional["Bluesky"] = None

    @staticmethod
    def from_dict(obj: Any) -> "Bluesky":
        bluesky_item = MetadataItem.from_dict(obj)
        bluesky_item.cid = obj.get("cid")
        bluesky_item.author_did = obj.get("author_did")
        return Bluesky(
            url=bluesky_item.url,
            title=bluesky_item.title,
            author=bluesky_item.author,
            author_url=bluesky_item.author_url,
            telegraph_url=bluesky_item.telegraph_url,
            text=bluesky_item.text,
            content=bluesky_item.content,
            media_files=bluesky_item.media_files,
            category=bluesky_item.category,
            message_type=bluesky_item.message_type,
            cid=bluesky_item.cid,
            author_did=bluesky_item.author_did,
        )

    def to_dict(self) -> dict:
        result: dict = super().to_dict()
        result["cid"] = self.cid
        result["author_did"] = self.author_did
        if self.retweet_post:
            result["retweet_post"] = self.retweet_post.to_dict()
        return result

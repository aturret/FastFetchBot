from typing import Optional, Any
from datetime import datetime

from odmantic import Model, Field

from app.models.metadata_item import MediaFile, MessageType
from app.utils.parse import get_html_text_length


class Metadata(Model):
    title: str = Field(default="untitled")
    message_type: MessageType = MessageType.SHORT
    author: Optional[str] = None
    author_url: Optional[str] = None
    text: Optional[str] = None
    text_length: Optional[int] = Field(ge=0)
    content: Optional[str] = None
    content_length: Optional[int] = Field(ge=0)
    category: Optional[str] = None
    source: Optional[str] = None
    media_files: Optional[list[MediaFile]] = None
    telegraph_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    scrape_status: bool = False

    def __post_init__(self, **data: Any):
        if data.get("text"):
            self.text_length = get_html_text_length(data["text"])
        if data.get("content"):
            self.content_length = get_html_text_length(data["content"])

    #
    @staticmethod
    def from_dict(obj: Any) -> "Metadata":
        assert isinstance(obj, dict)
        return Metadata(**obj)

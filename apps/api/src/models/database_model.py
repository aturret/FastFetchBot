from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field
from beanie import Document, Indexed, Insert, after_event, before_event

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.parse import get_html_text_length


class Metadata(Document):
    title: str = Field(default="untitled")
    message_type: MessageType = MessageType.SHORT
    url: str
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

    @before_event(Insert)
    def get_text_length(self):
        self.text_length = get_html_text_length(self.text)
        self.content_length = get_html_text_length(self.content)

    #
    @staticmethod
    def from_dict(obj: Any) -> "Metadata":
        assert isinstance(obj, dict)
        return Metadata(**obj)


document_list = [Metadata]

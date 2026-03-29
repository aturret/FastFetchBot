from typing import Optional, Any
from datetime import datetime

from pydantic import Field
from pydantic.dataclasses import dataclass as pydantic_dataclass
from beanie import Document, Insert, before_event

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.parse import get_html_text_length


@pydantic_dataclass
class DatabaseMediaFile(MediaFile):
    """Media file for MongoDB storage. Inherits all MediaFile fields and adds
    ``file_key`` for the S3 object key after upload."""

    file_key: Optional[str] = None


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
    media_files: Optional[list[DatabaseMediaFile]] = None
    telegraph_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    scrape_status: bool = False

    @before_event(Insert)
    def prepare_for_insert(self):
        self.text_length = get_html_text_length(self.text)
        self.content_length = get_html_text_length(self.content)
        if self.media_files:
            self.media_files = [
                item if isinstance(item, DatabaseMediaFile)
                else DatabaseMediaFile(**item if isinstance(item, dict) else item.__dict__)
                for item in self.media_files
            ]

    @staticmethod
    def from_dict(obj: Any) -> "Metadata":
        assert isinstance(obj, dict)
        return Metadata(**obj)


document_list = [Metadata]

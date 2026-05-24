from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, List, TypeVar, Callable, Type, cast, Union, Optional

from pydantic import BaseModel

"""
MetadataItem is a dataclass that represents a single item for our services. It would be saved in the database.
The MetadataItem is used to send to the telegram bot. Users can use the metadata to define their own message template.
If the program doesn't find the attribute in the dict_data, it will use the default value in case of KeyError.
"""

T = TypeVar("T")


def from_str(x: Any) -> str:
    if x is None:
        return ""
    assert isinstance(x, str)
    return x


def from_optional_int(x: Any) -> Optional[int]:
    if isinstance(x, bool) or not isinstance(x, int) or x <= 0:
        return None
    return x


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@unique
class MessageType(str, Enum):
    SHORT = "short"
    LONG = "long"


@dataclass
class MediaFile:
    media_type: str
    url: str
    original_url: Optional[str] = None
    caption: Optional[str] = None
    telegram_file_id: Optional[str] = None

    @staticmethod
    def from_dict(obj: Any) -> "MediaFile":
        assert isinstance(obj, dict)
        media_type = from_str(obj.get("media_type"))
        url = from_str(obj.get("url"))
        caption = from_str(obj.get("caption"))
        telegram_file_id = obj.get("telegram_file_id")
        return MediaFile(media_type, url, caption=caption, telegram_file_id=telegram_file_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["media_type"] = from_str(self.media_type)
        result["url"] = from_str(self.url)
        result["caption"] = self.caption
        if self.telegram_file_id is not None:
            result["telegram_file_id"] = self.telegram_file_id
        return result


@dataclass
class MetadataItem:
    url: str
    telegraph_url: Optional[str]
    content: Optional[str]
    text: Optional[str]
    media_files: List[MediaFile]
    author: str
    title: str
    author_url: Optional[str]
    category: str
    message_type: Optional[MessageType]
    timestamp: Optional[int] = None

    @staticmethod
    def from_dict(obj: Any) -> "MetadataItem":
        assert isinstance(obj, dict)
        url = from_str(obj.get("url"))
        telegraph_url = from_str(obj.get("telegraph_url"))
        content = from_str(obj.get("content"))
        text = from_str(obj.get("text"))
        media_files = from_list(MediaFile.from_dict, obj.get("media_files"))
        author = from_str(obj.get("author"))
        title = from_str(obj.get("title"))
        author_url = from_str(obj.get("author_url"))
        category = from_str(obj.get("category"))
        message_type = MessageType(obj.get("message_type"))
        timestamp = from_optional_int(obj.get("timestamp"))
        return MetadataItem(
            url,
            telegraph_url,
            content,
            text,
            media_files,
            author,
            title,
            author_url,
            category,
            message_type,
            timestamp,
        )

    def to_dict(self) -> dict:
        timestamp = from_optional_int(getattr(self, "timestamp", None))
        message_type = getattr(self, "message_type", None)
        message_type_value = (
            message_type.value if isinstance(message_type, MessageType) else message_type
        )
        result: dict = {
            "url": from_str(getattr(self, "url", "")),
            "telegraph_url": "",
            "content": from_str(getattr(self, "content", "")),
            "text": from_str(getattr(self, "text", "")),
            "media_files": from_list(
                lambda x: to_class(MediaFile, x), getattr(self, "media_files", [])
            ),
            "author": from_str(getattr(self, "author", "")),
            "title": from_str(getattr(self, "title", "")),
            "author_url": from_str(getattr(self, "author_url", "")),
            "category": from_str(getattr(self, "category", "")),
            "message_type": message_type_value,
            "timestamp": timestamp,
        }
        return result


def metadata_item_from_dict(s: Any) -> MetadataItem:
    return MetadataItem.from_dict(s)


def metadata_item_to_dict(x: MetadataItem) -> Any:
    return to_class(MetadataItem, x)

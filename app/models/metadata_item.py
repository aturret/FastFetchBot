from dataclasses import dataclass
from typing import Any, List, TypeVar, Callable, Type, cast


T = TypeVar("T")


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@dataclass
class MediaFile:
    media_type: str
    url: str
    caption: str

    @staticmethod
    def from_dict(obj: Any) -> 'MediaFile':
        assert isinstance(obj, dict)
        media_type = from_str(obj.get("media_type"))
        url = from_str(obj.get("url"))
        caption = from_str(obj.get("caption"))
        return MediaFile(media_type, url, caption)

    def to_dict(self) -> dict:
        result: dict = {}
        result["media_type"] = from_str(self.media_type)
        result["url"] = from_str(self.url)
        result["caption"] = from_str(self.caption)
        return result


@dataclass
class MetadataItem:
    url: str
    turl: str
    content: str
    text: str
    media_files: List[MediaFile]
    author: str
    title: str
    author_url: str
    type: str

    @staticmethod
    def from_dict(obj: Any) -> 'MetadataItem':
        assert isinstance(obj, dict)
        url = from_str(obj.get("url"))
        turl = from_str(obj.get("turl"))
        content = from_str(obj.get("content"))
        text = from_str(obj.get("text"))
        media_files = from_list(MediaFile.from_dict, obj.get("media_files"))
        author = from_str(obj.get("author"))
        title = from_str(obj.get("title"))
        author_url = from_str(obj.get("author_url"))
        type = from_str(obj.get("type"))
        return MetadataItem(url, turl, content, text, media_files, author, title, author_url, type)

    def to_dict(self) -> dict:
        result: dict = {}
        result["url"] = from_str(self.url)
        result["turl"] = from_str(self.turl)
        result["content"] = from_str(self.content)
        result["text"] = from_str(self.text)
        result["media_files"] = from_list(lambda x: to_class(MediaFile, x), self.media_files)
        result["author"] = from_str(self.author)
        result["title"] = from_str(self.title)
        result["author_url"] = from_str(self.author_url)
        result["type"] = from_str(self.type)
        return result


def metadata_item_from_dict(s: Any) -> MetadataItem:
    return MetadataItem.from_dict(s)


def metadata_item_to_dict(x: MetadataItem) -> Any:
    return to_class(MetadataItem, x)

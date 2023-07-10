import re
from dataclasses import dataclass
from typing import Any, TypeVar, Type, cast

T = TypeVar("T")


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@dataclass
class UrlMetadata:
    url: str
    category: str
    type: str

    def __init__(self, url: str, category: str, the_type: str) -> None:
        self.url = url
        self.category = category
        self.type = the_type

    @staticmethod
    def from_dict(obj: Any) -> "UrlMetadata":
        assert isinstance(obj, dict)
        url = from_str(obj.get("url"))
        category = from_str(obj.get("category"))
        the_type = from_str(obj.get("type"))
        return UrlMetadata(url, category, the_type)

    def to_dict(self) -> dict:
        result: dict = {}
        result["url"] = from_str(self.url)
        result["category"] = from_str(self.category)
        result["type"] = from_str(self.type)
        return result


def url_metadata_from_dict(s: Any) -> UrlMetadata:
    return UrlMetadata.from_dict(s)


def url_metadata_to_dict(x: UrlMetadata) -> Any:
    return to_class(UrlMetadata, x)
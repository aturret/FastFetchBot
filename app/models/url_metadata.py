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
    source: str
    type: str

    def __init__(self, url: str, source: str, the_type: str) -> None:
        self.url = url
        self.source = source
        self.type = the_type

    @staticmethod
    def from_dict(obj: Any) -> "UrlMetadata":
        assert isinstance(obj, dict)
        url = from_str(obj.get("url"))
        source = from_str(obj.get("source"))
        the_type = from_str(obj.get("type"))
        return UrlMetadata(url, source, the_type)

    def to_dict(self) -> dict:
        result: dict = {}
        result["url"] = from_str(self.url)
        result["source"] = from_str(self.source)
        result["type"] = from_str(self.type)
        return result


def url_metadata_from_dict(s: Any) -> UrlMetadata:
    return UrlMetadata.from_dict(s)


def url_metadata_to_dict(x: UrlMetadata) -> Any:
    return to_class(UrlMetadata, x)

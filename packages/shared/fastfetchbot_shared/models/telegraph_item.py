from dataclasses import dataclass
from typing import Any, TypeVar, Type, cast

"""
The TelegraphItem is a class for generating a Telegraph page.
If the program doesn't find the attribute in the dict_data, it will use the default value in case of KeyError.
"""

T = TypeVar("T")


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@dataclass
class TelegraphItem:
    title: str
    url: str
    author: str
    author_url: str
    category: str
    content: str

    @staticmethod
    def from_dict(obj: Any) -> 'TelegraphItem':
        assert isinstance(obj, dict)
        title = from_str(obj.get("title"))
        url = from_str(obj.get("url"))
        author = from_str(obj.get("author"))
        author_url = from_str(obj.get("author_url"))
        category = from_str(obj.get("category"))
        content = from_str(obj.get("content"))
        return TelegraphItem(title, url, author, author_url, category, content)

    def to_dict(self) -> dict:
        result: dict = {}
        result["title"] = from_str(self.title)
        result["url"] = from_str(self.url)
        result["author"] = from_str(self.author)
        result["author_url"] = from_str(self.author_url)
        result["category"] = from_str(self.category)
        result["content"] = from_str(self.content)
        return result


def telegraph_item_from_dict(s: Any) -> TelegraphItem:
    return TelegraphItem.from_dict(s)


def telegraph_item_to_dict(x: TelegraphItem) -> Any:
    return to_class(TelegraphItem, x)

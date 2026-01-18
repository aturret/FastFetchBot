from dataclasses import dataclass
from typing import Any

from app.models.metadata_item import MetadataItem


@dataclass
class FirecrawlItem(MetadataItem):
    """
    FirecrawlItem: Data class for scraped content from Firecrawl.
    """
    id: str = ""
    raw_content: str = ""

    @staticmethod
    def from_dict(obj: Any) -> "FirecrawlItem":
        metadata_item = MetadataItem.from_dict(obj)
        return FirecrawlItem(
            url=metadata_item.url,
            title=metadata_item.title,
            author=metadata_item.author,
            author_url=metadata_item.author_url,
            telegraph_url=metadata_item.telegraph_url,
            text=metadata_item.text,
            content=metadata_item.content,
            media_files=metadata_item.media_files,
            category=metadata_item.category,
            message_type=metadata_item.message_type,
            id=obj.get("id", ""),
            raw_content=obj.get("raw_content", ""),
        )

    def to_dict(self) -> dict:
        result: dict = super().to_dict()
        result["id"] = self.id
        result["raw_content"] = self.raw_content
        return result

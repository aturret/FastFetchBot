from dataclasses import dataclass
from typing import Any

from fastfetchbot_shared.models.metadata_item import MetadataItem


@dataclass
class GeneralItem(MetadataItem):
    """
    GeneralItem: Data class for scraped content from general webpage scrapers.
    """
    id: str = ""
    raw_content: str = ""
    scraper_type: str = ""  # Which scraper was used (e.g., "firecrawl", "zyte", etc.)

    @staticmethod
    def from_dict(obj: Any) -> "GeneralItem":
        metadata_item = MetadataItem.from_dict(obj)
        return GeneralItem(
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
            scraper_type=obj.get("scraper_type", ""),
        )

    def to_dict(self) -> dict:
        result: dict = super().to_dict()
        result["id"] = self.id
        result["raw_content"] = self.raw_content
        result["scraper_type"] = self.scraper_type
        return result

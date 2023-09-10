from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field
from beanie import Document, Indexed


class TelegramMessage(Document):
    date: Indexed(datetime) = Field(default_factory=datetime.utcnow)
    user: str = Field(default="unknown")
    text: str = Field(default="unknown")


document_list = [TelegramMessage]

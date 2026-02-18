from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field
from beanie import Document, Indexed


class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramMessage(Document):
    date: Indexed(datetime) = Field(default_factory=datetime.utcnow)
    chat: TelegramChat
    user: TelegramUser
    text: str = Field(default="unknown")


document_list = [TelegramMessage]

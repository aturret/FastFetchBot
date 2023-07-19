# TODO: copy the html-to-telegraph package and modify it to fit the asynchronous model
from typing import Any

from app.services.html_telegraph_poster_async import upload_to_telegraph, AsyncTelegraphPoster
from app.models.telegraph_item import TelegraphItem, from_str


class Telegraph(TelegraphItem):

    def __init__(self, title: str, url: str, author: str, author_url: str, category: str, content: str):
        self.telegraph = AsyncTelegraphPoster(use_api=True)
        self.title = title
        self.url = url
        self.author = author
        self.author_url = author_url
        self.category = category
        self.content = content

    @staticmethod
    def from_dict(obj: Any) -> 'Telegraph':
        assert isinstance(obj, dict)
        title = from_str(obj.get("title"))
        url = from_str(obj.get("url"))
        author = from_str(obj.get("author"))
        author_url = from_str(obj.get("author_url"))
        category = from_str(obj.get("category"))
        content = from_str(obj.get("content"))
        return Telegraph(title, url, author, author_url, category, content)

    async def get_telegraph(self):
        await self.telegraph.create_api_token(short_name=self.author[0:14], author_name=self.author)
        telegraph_post = await self.telegraph.post(title=self.title,
                                                   author=self.author,
                                                   author_url=self.author_url,
                                                   text=self.content)
        telegraph_url = telegraph_post['url']
        return telegraph_url

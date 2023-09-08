import httpx
from bs4 import BeautifulSoup
import jmespath

from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.utils.config import HEADERS
from app.utils.logger import logger
from app.utils.parse import get_html_text_length
from app.config import INOREADER_APP_ID, INOREADER_APP_KEY, INOREADER_EMAIL, INOREADER_PASSWORD

INOREADER_BROADCAST_URL = "https://www.inoreader.com/reader/api/0/stream/contents/user/-/state/com.google/broadcast"
INOREADER_LOGIN_URL = "https://www.inoreader.com/accounts/ClientLogin"


class Inoreader(MetadataItem):
    def __init__(self, url: str = None, data: dict = None, **kwargs):
        if url:
            self.url = url
        if data:
            self.title = data.get("title", "")
            self.message = data.get("message", "")
            self.author = data.get("author", "")
            self.author_url = data.get("author_url", "")
            self.category = data.get("category", "")
            self.raw_content = data.get("content", "")
            self.content = self.raw_content
        if kwargs.get("category"):
            self.category = kwargs["category"]
        self.media_files = []
        self.message_type = MessageType.LONG

    def _from_data(self, data: dict):
        self.title = data.get("title", "")
        self.message = data.get("message", "")
        self.author = data.get("author", "")
        self.author_url = data.get("author_url", "")
        self.category = data.get("category", "")
        self.raw_content = data.get("content", "")
        self.content = self.raw_content

    async def get_item(self, api: bool = False) -> dict:
        if api:
            data = await self.request_api_info()

        self._resolve_media_files()
        if get_html_text_length(self.content) < 400:
            self.message_type = MessageType.SHORT
        metadata_dict = self.to_dict()
        metadata_dict["message"] = self.message
        return metadata_dict

    def _resolve_media_files(self):
        soup = BeautifulSoup(self.raw_content, "html.parser")
        for img in soup.find_all("img"):
            self.media_files.append(MediaFile(url=img["src"], media_type="image"))
            img.extract()
        for video in soup.find_all("video"):
            self.media_files.append(MediaFile(url=video["src"], media_type="video"))
            video.extract()
        for tags in soup.find_all("p", "span"):
            tags.unwrap()
        self.text = str(soup)
        self.text = '<a href="' + self.url + '">' + self.author + "</a>: " + self.text

    @staticmethod
    async def request_api_info() -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                INOREADER_LOGIN_URL,
                params={
                    "Email": INOREADER_EMAIL,
                    "Passwd": INOREADER_PASSWORD,
                },
            )
            authorization = resp.text.split("\n")[2].split("=")[1]
        async with httpx.AsyncClient() as client:
            headers = HEADERS
            headers['Authorization'] = f'GoogleLogin auth={authorization}'
            resp = await client.get(
                INOREADER_BROADCAST_URL,
                params={
                    "AppId": INOREADER_APP_ID,
                    "AppKey": INOREADER_APP_KEY,
                    "comments": 1,
                    "n": 1,
                },
                headers=headers,
            )
            logger.debug(resp.text)
            data = resp.json()
            expression = f"""{{
                        "aurl": items[0].canonical[0].href,
                        "title": items[0].title,
                        "author": items[0].origin.title,
                        "author_url": items[0].origin.htmlUrl,
                        "content": items[0].summary.content,
                        "category": items[0].categories[-1],
                        "message": items[0].comments[0].commentBody
                    }}"""
            data = jmespath.search(expression, data)
            data['category'] = data['category'].split('/')[-1]
        return data

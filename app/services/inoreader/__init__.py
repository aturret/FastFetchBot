from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
import jmespath
from httpx import Response

from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.utils.config import HEADERS
from app.utils.logger import logger
from app.utils.parse import get_html_text_length
from app.config import (
    INOREADER_APP_ID,
    INOREADER_APP_KEY,
    INOREADER_EMAIL,
    INOREADER_PASSWORD,
)

INOREADER_CONTENT_URL = "https://www.inoreader.com/reader/api/0/stream/contents/"
TAG_PATH = "user/-/label/"
OTHER_PATH = "user/-/state/com.google/"
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
            data = await self.get_api_item_data()
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
        for tags in soup.find_all(["p", "span"]):
            tags.unwrap()
        self.text = str(soup)
        self.text = '<a href="' + self.url + '">' + self.author + "</a>: " + self.text

    @staticmethod
    def get_stream_id(
        stream_type: str = "broadcast", tag: str = None, feed: str = None
    ) -> str:
        if stream_type == "feed":
            stream_id = feed
        elif stream_type == "tag":
            stream_id = TAG_PATH + tag
        else:
            stream_id = OTHER_PATH + stream_type
        stream_id = quote(stream_id)
        return stream_id

    @staticmethod
    async def mark_all_as_read(stream_id: str, timestamp: int = 0) -> None:
        request_url = "https://www.inoreader.com/reader/api/0/mark-all-as-read"
        params = {"s": stream_id, "ts": timestamp}
        resp = await Inoreader.get_api_info(url=request_url, params=params)
        logger.debug(resp.text)

    @staticmethod
    async def get_api_item_data(
        stream_type: str = "broadcast",
        tag: str = None,
        feed: str = None,
        params: dict = None,
    ) -> dict:
        stream_id = Inoreader.get_stream_id(stream_type=stream_type, tag=tag, feed=feed)
        request_url = INOREADER_CONTENT_URL + stream_id
        default_params = {
            "comments": 1,
            "n": 10,
            "r": "o",
            "xt": "user/-/state/com.google/read",
        }
        if params:
            default_params.update(params)
        params = default_params
        resp = await Inoreader.get_api_info(url=request_url, params=params)
        logger.debug(resp.text)
        data = resp.json()
        expression = """
                    items[].{
                    "aurl": canonical[0].href,
                    "title": title,
                    "author": origin.title,
                    "author_url": origin.htmlUrl,
                    "content": summary.content,
                    "category": categories[-1],
                    "message": comments[0].commentBody,
                    "timestamp": updated
                    }
                """
        data = jmespath.search(expression, data)
        for item in data:
            item["category"] = item["category"].split("/")[-1]
        return data

    @staticmethod
    async def get_api_info(
        url: str,
        params=None,
    ) -> Response:
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
            headers["Authorization"] = f"GoogleLogin auth={authorization}"
            params = params or {}
            params.update(
                {
                    "AppId": INOREADER_APP_ID,
                    "AppKey": INOREADER_APP_KEY,
                }
            )
            resp = await client.get(
                url=url,
                params=params,
                headers=headers,
            )
            return resp

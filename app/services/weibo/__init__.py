import json
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.models.metadata_item import MetadataItem
from app.utils.config import CHROME_USER_AGENT
from app.utils.network import get_response_json
from config import AJAX_HOST, AJAX_LONGTEXT_HOST, WEIBO_WEB_HOST


class Weibo(MetadataItem):
    def __init__(
        self,
        url: str,
        method: Optional[str] = "api",
        scraper: Optional[str] = "requests",
        user_agent: Optional[dict] = CHROME_USER_AGENT,
        cookies: Optional[str] = None,
    ):
        self.url = url
        self.method = method
        self.scraper = scraper
        self.headers = {"User-Agent": user_agent, "Cookie": cookies}
        url_parser = urlparse(url)
        self.id = url_parser.path.split("/")[-1]
        self.ajax_url = AJAX_HOST + self.id
        self.ajax_longtext_url = AJAX_LONGTEXT_HOST + self.id

    async def get_weibo(self):
        # TODO: get weibo info than parse it and return the result
        pass

    async def get_weibo_info(self) -> dict:
        if self.method == "webpage":
            url = WEIBO_WEB_HOST + self.id
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 302:
                    new_url = response.headers["Location"]
                    print(f"Redirected to {new_url}... following")
                    response = await client.get(new_url, headers=self.headers)
            html = response.text
            html = html[html.find('"status":') :]
            html = html[: html.rfind('"hotScheme"')]
            html = html[: html.rfind(",")]
            html = html[: html.rfind("][0] || {};")]
            html = "{" + html
            try:
                js = json.loads(html, strict=False)
                print(js)
                weibo_info = js.get("status")
            except:
                weibo_info = {}
        elif self.method == "a  pi":
            ajax_info = await get_response_json(self.ajax_url, headers=self.headers)
        return weibo_info

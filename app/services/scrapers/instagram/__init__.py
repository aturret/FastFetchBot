# TODO: https://rapidapi.com/arraybobo/api/instagram-scraper-2022
import re
from typing import Any, Optional
from urllib.parse import urlparse

from html import escape

from app.models.metadata_item import MetadataItem, MessageType, MediaFile
from app.utils.network import get_response
from app.utils.parse import get_html_text_length
from app.utils.logger import logger
from .config import API_HEADERS_LIST, ALL_SCRAPERS
from app.config import X_RAPIDAPI_KEY


class Instagram(MetadataItem):
    def __init__(self, url: str, data: Optional[Any] = None, **kwargs):
        self.url = url
        self.category = "instagram"
        # auxiliary variables
        self.urlparser = urlparse(url)
        self.post_id = re.sub(r".*((/p/)|(/reel/))", "", self.urlparser.path).replace(
            "/", ""
        )
        self.message_type = MessageType.SHORT

    async def get_item(self):
        await self.get_instagram()
        return self.to_dict()

    async def get_instagram(self):
        self._check_instagram_url()
        await self._get_instagram_info()

    def _check_instagram_url(self):
        if (
            self.urlparser.path.find("p") != -1
            or self.urlparser.path.find("reel") != -1
        ):
            self.ins_type = "post"
        if self.urlparser.path.find("stories") != -1:
            self.ins_type = "story"

    async def _get_instagram_info(self):
        ins_functions_dict = {
            "post": self._get_post_info,
            "story": self._get_story_info,
        }
        ins_info = await ins_functions_dict[self.ins_type]()
        self._process_ins_info(ins_info)

    async def _get_post_info(self) -> dict:
        ins_info = {}
        for scraper in ALL_SCRAPERS:
            self.scraper = scraper
            self.host = API_HEADERS_LIST[self.scraper]["host"]
            self.headers = {
                "X-RapidAPI-Key": X_RAPIDAPI_KEY,
                "X-RapidAPI-Host": API_HEADERS_LIST[self.scraper]["top_domain"],
                "content-type": "application/octet-stream",
            }
            params_value = self.url if self.scraper == "looter2" else self.post_id
            self.params = {API_HEADERS_LIST[self.scraper]["params"]: params_value}
            response = await get_response(
                url=self.host, headers=self.headers, params=self.params
            )
            if response.status_code != 200:
                logger.error(
                    "get_ins_post_item error: %s %s", self.scraper, response.status_code
                )
                continue
            else:
                ins_data = response.json()
                logger.debug("get_ins_post_item: %s %s", self.params, ins_data)
                if type(ins_data) == dict and "graphql" in ins_data:
                    ins_data = ins_data["graphql"]["shortcode_media"]
                elif type(ins_data) == dict and "data" in ins_data:
                    ins_data = ins_data["data"]
                elif (
                    type(ins_data) == dict
                    and "status" in ins_data
                    and ins_data["status"] is False
                ):
                    print("get_ins_post_item error: ", self.scraper)
                    continue
                elif type(ins_data) == str and "400" in ins_data:
                    print("get_ins_post_item error: ", self.scraper, ins_data)
                    continue
            if (
                self.scraper == "looter2"
                or self.scraper == "ins191"
                or self.scraper == "ins130"
            ):
                ins_info = self._get_ins_post_looter2(ins_data)
            elif self.scraper == "ins28" or self.scraper == "scraper2" or self.scraper == "api2":
                ins_info = self._get_ins_post_ins28_scraper2(ins_data)
            break
        return ins_info

    def _process_ins_info(self, ins_info: dict):
        self.__dict__.update(ins_info)
        self.title = self.author + "'s Instagram post"
        self.text = escape(self.text)
        self.text = "<a href='" + self.url + "'>" + self.title + "</a>\n" + self.text
        if get_html_text_length(self.text) > 500:
            self.message_type = MessageType.LONG

    @staticmethod
    def _get_ins_post_looter2(ins_data: dict) -> dict:
        ins_info = {}
        ins_text_data = (
            ins_data["edge_media_to_caption"]["edges"][0]["node"]["text"]
            if ins_data["edge_media_to_caption"]["edges"]
            else ""
        )
        ins_info["content"] = ""
        ins_info["text"] = ins_text_data
        ins_info["author"] = ins_data["owner"]["username"]
        if ins_data["owner"]["full_name"]:
            ins_info["author"] += "(" + ins_data["owner"]["full_name"] + ")"
        ins_info["author_url"] = (
            "https://www.instagram.com/" + ins_data["owner"]["username"] + "/"
        )
        ins_info["media_files"] = []
        if ins_data["__typename"] == "GraphVideo":
            ins_info["media_files"].append(
                MediaFile.from_dict(
                    {"media_type": "video", "url": ins_data["video_url"], "caption": ""}
                )
            ) if ins_data["video_url"] else []
            ins_info["content"] += (
                '<video controls src="' + ins_data["video_url"] + '"></video>'
            )
        elif ins_data["__typename"] == "GraphImage":
            ins_info["media_files"].append(
                MediaFile.from_dict(
                    {
                        "media_type": "image",
                        "url": ins_data["display_url"],
                        "caption": "",
                    }
                )
            )
            ins_info["content"] += (
                '<img src="' + ins_data["display_url"] + '">'
                if ins_data["display_url"]
                else ""
            )
        elif ins_data["__typename"] == "GraphSidecar":
            for item in ins_data["edge_sidecar_to_children"]["edges"]:
                if item["node"]["__typename"] == "GraphVideo":
                    ins_info["media_files"].append(
                        MediaFile.from_dict(
                            {
                                "media_type": "video",
                                "url": item["node"]["video_url"],
                                "caption": "",
                            }
                        )
                    )
                    ins_info["content"] += (
                        '<video controls src="'
                        + item["node"]["video_url"]
                        + '"></video>'
                    )
                elif item["node"]["__typename"] == "GraphImage":
                    ins_info["media_files"].append(
                        MediaFile.from_dict(
                            {
                                "media_type": "image",
                                "url": item["node"]["display_url"],
                                "caption": "",
                            }
                        )
                    )
                    ins_info["content"] += (
                        '<img src="' + item["node"]["display_url"] + '">'
                    )
        ins_info["content"] += ins_text_data
        ins_info["status"] = True
        return ins_info

    @staticmethod
    def _get_ins_post_ins28_scraper2(ins_data):
        ins_info = {}
        ins_text_data = (
            ins_data["items"][0]["caption"]["text"]
            if ins_data["items"][0]["caption"]
            else ""
        )
        ins_info["content"] = ""
        ins_info["text"] = ins_text_data
        ins_info["author"] = ins_data["items"][0]["user"]["username"]
        if ins_data["items"][0]["user"]["full_name"]:
            ins_info["author"] += "(" + ins_data["items"][0]["user"]["full_name"] + ")"
        ins_info["author_url"] = (
            "https://www.instagram.com/"
            + ins_data["items"][0]["user"]["username"]
            + "/"
        )
        ins_info["media_files"] = []
        if ins_data["items"][0]["media_type"] == 2:
            ins_info["media_files"].append(
                MediaFile.from_dict(
                    {
                        "media_type": "video",
                        "url": ins_data["items"][0]["video_versions"][0]["url"],
                        "caption": "",
                    }
                )
            )
            ins_info["content"] += (
                '<video controls src="'
                + ins_data["items"][0]["video_versions"][0]["url"]
                + '"></video>'
            )
        elif ins_data["items"][0]["media_type"] == 1:
            ins_info["media_files"].append(
                MediaFile.from_dict(
                    {
                        "media_type": "image",
                        "url": ins_data["items"][0]["image_versions2"]["candidates"][0][
                            "url"
                        ],
                        "caption": "",
                    }
                )
            )
            ins_info["content"] += (
                '<img src="'
                + ins_data["items"][0]["image_versions2"]["candidates"][0]["url"]
                + '">'
            )
        elif ins_data["items"][0]["media_type"] == 8:
            for item in ins_data["items"][0]["carousel_media"]:
                if item["media_type"] == 2:
                    ins_info["media_files"].append(
                        MediaFile.from_dict(
                            {
                                "media_type": "video",
                                "url": item["video_versions"][0]["url"],
                                "caption": "",
                            }
                        )
                    )
                    ins_info["content"] += (
                        '<video controls src="'
                        + item["video_versions"][0]["url"]
                        + '"></video>'
                    )
                elif item["media_type"] == 1:
                    ins_info["media_files"].append(
                        MediaFile.from_dict(
                            {
                                "media_type": "image",
                                "url": item["image_versions2"]["candidates"][0]["url"],
                                "caption": "",
                            }
                        )
                    )
                    ins_info["content"] += (
                        '<img src="'
                        + item["image_versions2"]["candidates"][0]["url"]
                        + '">'
                    )
        ins_info["content"] += ins_text_data
        ins_info["status"] = True
        return ins_info

    async def _get_story_info(self):
        pass

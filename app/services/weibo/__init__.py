import json
from typing import Optional, Any
from urllib.parse import urlparse

import httpx
import jmespath
from bs4 import BeautifulSoup
from lxml import html

from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.utils.config import CHROME_USER_AGENT
from app.utils.network import get_response_json
from app.utils.parse import get_html_text_length
from .config import (
    AJAX_HOST,
    AJAX_LONGTEXT_HOST,
    WEIBO_WEB_HOST,
    WEIBO_HOST,
    WEIBO_TEXT_LIMIT,
)
from app.config import JINJA2_ENV
from ...utils.logger import logger

short_text_template = JINJA2_ENV.get_template("weibo_short_text.jinja2")
content_template = JINJA2_ENV.get_template("weibo_content.jinja2")


class Weibo(MetadataItem):
    def __init__(
        self,
        url: str,
        data: Any,
        method: Optional[str] = "api",
        scraper: Optional[str] = "requests",
        user_agent: Optional[dict] = CHROME_USER_AGENT,
        cookies: Optional[str] = None,
    ):
        # basic info
        self.url = url
        self.method = method
        self.scraper = scraper
        self.text = ""
        self.headers = {"User-Agent": user_agent}
        self.headers["Cookies"] = cookies if cookies else ""
        self.url_parser = urlparse(url)
        self.id = self.url_parser.path.split("/")[-1]
        self.ajax_url = AJAX_HOST + self.id
        self.ajax_longtext_url = AJAX_LONGTEXT_HOST + self.id
        # metadata
        self.media_files = []
        self.author = ""
        self.author_url = ""
        self.category = "weibo"
        # auxiliary fields
        self.retweeted_info = None

    async def get_item(self) -> dict:
        await self.get_weibo()
        return self.to_dict()

    async def get_weibo(self) -> None:
        try:
            weibo_info = await self._get_weibo_info()
        except:
            weibo_info = await self._get_weibo_info(
                method="webpage" if self.method == "api" else "api"
            )
        await self._process_weibo_item(weibo_info)

    async def _get_weibo_info(self, method=None) -> dict:
        if not method:
            method = self.method
        if method == "webpage":
            weibo_info = await self._get_weibo_info_webpage()
        elif method == "api":
            weibo_info = await self._get_weibo_info_api()
        weibo_info = self._parse_weibo_info(weibo_info)
        return weibo_info

    async def _get_weibo_info_webpage(self) -> dict:
        url = WEIBO_WEB_HOST + self.id
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            if response.status_code == 302:  # redirect
                new_url = response.headers["Location"]
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
        return weibo_info

    async def _get_weibo_info_api(self) -> dict:
        ajax_json = await get_response_json(self.ajax_url, headers=self.headers)
        logger.debug(f"weibo ajax_json info by api: {ajax_json}")
        if not ajax_json or ajax_json["ok"] == 0:
            return await self._get_weibo_info(method="webpage")
        return ajax_json

    async def _get_long_weibo_info_api(self) -> dict:
        ajax_json = await get_response_json(self.ajax_longtext_url, headers=self.headers)
        logger.debug(f"weibo ajax_json info by api: {ajax_json}")
        return ajax_json

    async def _process_weibo_item(self, weibo_info: dict) -> None:
        self.id = str(weibo_info.get("id"))
        # get user info
        self.user_id = weibo_info.get("user_id")
        self.author = weibo_info.get("author")
        self.author_url = WEIBO_HOST + weibo_info.get("author_url")
        self.title = self.author + "的微博"
        # get basic metadata
        self.date = weibo_info.get("created", None)
        self.source = weibo_info.get("source", None)
        self.region_name = weibo_info.get("region_name", None)
        self.attitudes_count = self._string_to_int(weibo_info.get("attitudes_count", 0))
        self.comments_count = self._string_to_int(weibo_info.get("comments_count", 0))
        self.reposts_count = self._string_to_int(weibo_info.get("reposts_count", 0))
        # resolve text
        # check if the weibo is longtext weibo (which means >140 characters so has an excerpt) or not
        text = weibo_info.get("text")
        if weibo_info["is_long_text"] or text.endswith("...展开"):
            # if a weibo has more than 9 pictures, the isLongText will be True even if it is not a longtext weibo
            # however, we cannot get the full text of such kind of weibo from longtext api (it will return None)
            # so, it is necessary to check if a weibo is a real longtext weibo or not for getting the full text
            try:
                longtext_info = await self._get_weibo_info(method="webpage")
                text = longtext_info.get("text")
            except Exception as e:
                logger.error(f"Failed to get longtext of weibo by webpage scraping.{e}")
                try:
                    longtext_info = await self._get_long_weibo_info_api()
                    text = longtext_info.get("longTextContent")
                except Exception as e:
                    logger.error(f"Failed to get longtext of weibo by api.{e}")
            # The two methods can both fail in some cases. So, we need to check if the text is None or not.
        else:
            # TODO: to add a branch to get the fulltext without using the webpage scraping. This branch needs cookies.
            pass
        cleaned_text, fw_pics = Weibo._weibo_html_text_clean(text)
        for pic in fw_pics:
            self.media_files.append(MediaFile(url=pic, media_type="image"))
        self.text += cleaned_text.replace("<br />", "<br>").replace("br/", "br")
        self.raw_content = self.text
        # resolve medias
        self.media_files = self._get_media_files(weibo_info)
        # render the text and content
        self.text = short_text_template.render(data=self.__dict__)
        self.text = self.text.replace("<br />", "\n").replace("<br>", "\n")
        for i in self.media_files:
            if i.media_type == "video":
                self.raw_content += f"<video src='{i.url}' controls='controls'></video>"
            elif i.media_type == "image":
                self.raw_content += f"<img src='{i.url}'></img>"
        self.content = content_template.render(data=self.__dict__)
        # resolve retweet
        if weibo_info.get("retweeted_status"):
            retweeted_weibo_item = Weibo(
                url=WEIBO_WEB_HOST + weibo_info["retweeted_status"]["idstr"]
            )
            await retweeted_weibo_item.get_weibo()
            self.retweeted_info = retweeted_weibo_item.__dict__
            self.text += self.retweeted_info["text"]
            self.content += "<hr>" + self.retweeted_info["content"]
            self.media_files += self.retweeted_info["media_files"]
        # type check
        self.message_type = (
            MessageType.LONG
            if get_html_text_length(self.text) > WEIBO_TEXT_LIMIT
            else MessageType.SHORT
        )

    @staticmethod
    def _parse_weibo_info(data: dict) -> dict:
        expression = f"""{{
            "id": id,
            "author": user.screen_name,
            "author_url": user.profile_url,
            "user_id": user.id,
            "created": created_at,
            "source": source,
            "region_name": region_name,
            "text": text,
            "text_raw": text_raw,
            "text_length": textLength,
            "is_long_text": isLongText,
            "pic_num": pic_num,
            "pic_video": pic_video,
            "pic_infos": pic_infos,
            "page_info": page_info,
            "mix_media_info": mix_media_info,
            "url_struct": url_struct,
            "attitudes_count": attitudes_count,
            "comments_count": comments_count,
            "reposts_count": reposts_count,
            "retweeted_status": retweeted_status
        }}"""
        weibo_info = jmespath.search(expression, data)
        return weibo_info

    def _get_media_files(self, weibo_info: dict) -> list:
        """
        The function is used to get all media files (pictures, videos, live photos) from a weibo item
        The design of weibo media files is very complicated and confusing. It can be divided from the following aspects:
        1. pic_infos: the media files of a weibo item are stored in pic_infos. This key only appears when the weibo item
        has only pictures. However, live photos, which is actually "videos", are also stored in pic_infos. So, we need
        to check the type and add it into the media files list.
        2. page_info: the media files of a weibo item are stored in page_info. This key only appears when the weibo item
        has only one video.
        3. mix_media_info: the media files of a weibo item are stored in mix_media_info. This key only appears when the
        weibo item has both pictures and videos.
        We separate the media files scraping process into three parts according to the above aspects. For keeping the
        order of the media files, we use a list to store the media files.
        :param weibo_info:
        :return: media_files: a list of media files
        """
        media_files = []
        media_files += self._get_pictures(weibo_info)
        media_files += self._get_videos(weibo_info)
        media_files += self._get_mix_media(weibo_info)
        return media_files

    @staticmethod
    def _get_pictures(weibo_info: dict) -> list:
        media_files = []
        if weibo_info.get("pics"):
            pic_info = weibo_info["pics"]
            for pic in pic_info:
                media_files.append(
                    MediaFile(url=pic["large"]["url"], media_type="image", caption="")
                )
        elif "pic_infos" in weibo_info and weibo_info.get("pic_num") > 0:
            pic_info = weibo_info["pic_infos"]
            for pic in pic_info:
                if pic_info[pic].get("type") == "pic":
                    media_files.append(
                        MediaFile(
                            url=pic_info[pic]["original"]["url"],
                            media_type="image",
                            caption="",
                        )
                    ) if pic_info[pic]["original"] else media_files.append(
                        MediaFile(
                            url=pic_info[pic]["large"]["url"],
                            media_type="image",
                            caption="",
                        )
                    )
                elif pic_info[pic].get("type") in ["live_photo", "livephoto"]:
                    media_files.append(
                        MediaFile(
                            url=pic_info[pic]["original"]["url"], media_type="image"
                        )
                    ) if pic_info[pic]["original"] else media_files.append(
                        MediaFile(pic_info[pic]["large"]["url"])
                    )
                    live_pic_url = pic_info[pic]["video"]["url"]
                    if not (live_pic_url[-4] == "." and live_pic_url[-3:] != "mp4"):
                        media_files.append(
                            MediaFile(url=pic_info[pic]["video"], media_type="video")
                        )
                elif pic_info[pic].get("type") == "gif":
                    media_files.append(
                        MediaFile(url=pic_info[pic]["video"], media_type="video")
                    )
        else:
            return media_files
        return media_files

    @staticmethod
    def _get_videos(weibo_info: dict) -> list:
        media_files, video_url_list = [], []
        if weibo_info.get("page_info"):
            if (
                weibo_info["page_info"].get("urls")
                or weibo_info["page_info"].get("media_info")
            ) and (
                weibo_info["page_info"].get("type") == "video"
                or weibo_info["page_info"].get("object_type") == "video"
            ):
                media_info = (
                    weibo_info["page_info"]["urls"]
                    if weibo_info["page_info"].get("urls")
                    else ""
                )
                if not media_info:
                    media_info = weibo_info["page_info"]["media_info"]
                video_url_keys = [
                    "mp4_720p_mp4",
                    "mp4_hd_url",
                    "hevc_mp4_hd",
                    "mp4_sd_url",
                    "mp4_ld_mp4",
                    "stream_url_hd",
                    "stream_url",
                ]
                for key in video_url_keys:
                    video_url = media_info.get(key)
                    if video_url:
                        break
                video_url_list.append(video_url)
        for url in video_url_list:
            media_files.append(MediaFile(url=url, media_type="video"))
        return media_files

    @staticmethod
    def _get_mix_media(weibo_info: dict) -> list:
        media_files = []
        if weibo_info.get("mix_media_info"):
            for item in weibo_info["mix_media_info"]["items"]:
                if item.get("type") == "pic":
                    media_files.append(
                        MediaFile(
                            url=item["data"]["original"]["url"], media_type="image"
                        )
                    ) if item["data"]["original"] else media_files.append(
                        MediaFile(url=item["data"]["large"]["url"], media_type="image")
                    )
                elif item.get("type") in ["live_photo", "livephoto"]:
                    media_files.append(
                        MediaFile(
                            url=item["data"]["original"]["url"], media_type="image"
                        )
                    ) if item["data"]["original"] else media_files.append(
                        MediaFile(url=item["data"]["large"]["url"], media_type="image")
                    )
                    media_files.append(
                        MediaFile(url=item["data"]["video"]["url"], media_type="video")
                    )
                elif item.get("type") == "gif":
                    media_files.append(
                        MediaFile(url=item["data"]["video"]["url"], media_type="video")
                    )
                elif item.get("type") == "video":
                    video_url = item.get("stream_url_hd")
                    video_keys = [
                        "mp4_720p_mp4",
                        "mp4_hd_url",
                        "hevc_mp4_hd",
                        "mp4_sd_url",
                        "mp4_ld_mp4",
                        "stream_url_hd",
                        "stream_url",
                    ]
                    for key in video_keys:
                        video_url = item["data"]["media_info"].get(key)
                        if video_url:
                            break
                    media_files.append(MediaFile(url=video_url, media_type="video"))
        return media_files

    @staticmethod
    def _string_to_int(string: str) -> int:
        """
        Convert Chinese numeric string to int
        :param string: str
        :return: int: int value of the string
        """
        if isinstance(string, int):
            return string
        elif string.endswith("万+"):
            string = string[:-2] + "0000"
        elif string.endswith("万"):
            string = float(string[:-1]) * 10000
        elif string.endswith("亿"):
            string = float(string[:-1]) * 100000000
        return int(string)

    @staticmethod
    def _get_live_photo(weibo_info: dict) -> list:
        live_photo_list = []
        live_photo = weibo_info.get("pic_video")
        if live_photo:
            prefix = "https://video.weibo.com/media/play?livephoto=//us.sinaimg.cn/"
            for i in live_photo.split(","):
                if len(i.split(":")) == 2:
                    url = prefix + i.split(":")[1] + ".mov"
                    live_photo_list.append(url)
            return live_photo_list

    @staticmethod
    def _weibo_html_text_clean(text, method="bs4"):
        if method == "bs4":
            return Weibo._weibo_html_text_clean_bs4(text)
        elif method == "lxml":
            return Weibo._weibo_html_text_clean_lxml(text)
        else:
            raise ValueError("method must be bs4 or lxml")

    @staticmethod
    def _weibo_html_text_clean_bs4(text):
        fw_pics = []
        soup = BeautifulSoup(text, "html.parser")
        for img in soup.find_all("img"):
            alt_text = img.get("alt", "")
            img.replace_with(alt_text)
        for a in soup.find_all("a"):
            if a.text == "查看图片":
                fw_pics.append(a.get("href"))
            if "/n/" in a.get("href") and a.get("usercard"):
                a["href"] = "https://weibo.com" + a.get("href")
        for i in soup.find_all("span"):
            i.unwrap()
        res = (
            str(soup)
            .replace('href="//', 'href="http://')
            .replace('href="/n/', 'href="http://weibo.com/n/')
        )
        return res, fw_pics

    @staticmethod
    def _weibo_html_text_clean_lxml(text):
        selector = html.fromstring(text)
        # remove all img tags and replace with alt text
        for img in selector.xpath("//img"):
            alt_text = img.get("alt", "")
        # get innerhtml pure text of the parent tag
        parent_text = img.getparent().text_content() if img.getparent() else ""
        replace_text = alt_text + parent_text
        text_node = html.fromstring(replace_text)
        img.addprevious(text_node)
        img.getparent().remove(img)
        # make text_node become pure text
        text_node.text = text_node.text_content()
        # return the html document after cleaning
        return html.tostring(selector, encoding="unicode")

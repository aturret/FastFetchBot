import json
from typing import Optional
from urllib.parse import urlparse

import httpx
import jmespath

from app.models.metadata_item import MetadataItem, MediaFile
from app.utils.config import CHROME_USER_AGENT
from app.utils.network import get_response_json
from .config import (AJAX_HOST, AJAX_LONGTEXT_HOST, WEIBO_WEB_HOST, WEIBO_HOST)


class Weibo(MetadataItem):
    def __init__(
            self,
            url: str,
            method: Optional[str] = "api",
            scraper: Optional[str] = "requests",
            user_agent: Optional[dict] = CHROME_USER_AGENT,
            cookies: Optional[str] = None,
    ):
        # basic info
        self.url = url
        self.method = method
        self.scraper = scraper
        self.headers = {"User-Agent": user_agent, "Cookie": cookies}
        self.url_parser = urlparse(url)
        self.id = self.url_parser.path.split("/")[-1]
        self.ajax_url = AJAX_HOST + self.id
        self.ajax_longtext_url = AJAX_LONGTEXT_HOST + self.id
        # metadata
        self.media_files = []
        self.author = ""
        self.author_url = ""

    async def get_weibo(self):
        weibo_info = await self._get_weibo_info()
        await self._process_weibo_item(weibo_info)
        return self.to_dict()

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
        html = html[html.find('"status":'):]
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
        print(ajax_json)
        if not ajax_json or ajax_json["ok"] == 0:
            return await self._get_weibo_info(method="webpage")
        return ajax_json

    async def _process_weibo_item(self, weibo_info: dict) -> None:
        self.id = weibo_info["id"]
        # get user info
        self.user_id = weibo_info["user_id"]
        self.author = weibo_info["author"]
        self.author_url = WEIBO_HOST + weibo_info["author_url"]
        self.title = self.author + "的微博"
        # get basic metadata
        self.date = weibo_info["created_at"]
        self.source = weibo_info["source"] if "source" in weibo_info else None
        self.region_name = weibo_info['region_name'] if 'region_name' in weibo_info else None
        self.attitudes_count = self._string_to_int(weibo_info.get("attitudes_count", 0))
        self.comments_count = self._string_to_int(weibo_info.get("comments_count", 0))
        self.reposts_count = self._string_to_int(weibo_info.get("reposts_count", 0))
        # resolve text
        # check if the weibo is longtext weibo (which means >140 characters so has an excerpt) or not
        if not weibo_info['is_long_text'] or (weibo_info['pic_num'] > 9 and weibo_info['is_long_text']):
            # if a weibo has more than 9 pictures, the isLongText will be True even if it is not a longtext weibo
            # however, we cannot get the full text of such kind of weibo from longtext api (it will return None)
            # so, it is necessary to check if a weibo is a real longtext weibo or not for getting the full text
            self.type = "short"

        # resolve pictures
        pic_list = self._get_pictures(weibo_info)

        # resolve videos
        video_list = self._get_videos(weibo_info)
        live_photo_list = self._get_live_photo(weibo_info)
        if live_photo_list:
            video_list += live_photo_list
        for video_url in video_list:
            self.media_files.append(MediaFile(url=video_url, media_type="video"))

        # resolve retweet
        if weibo_info.get("retweeted_status"):
            retweet_info = self._parse_weibo_info(weibo_info["retweeted_status"])

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

    @staticmethod
    def _get_pictures(weibo_info: dict) -> list:
        pic_list = []
        if weibo_info.get('pic_num'):
            for i in range(weibo_info['pic_num']):
                pic_url = weibo_info['pic_infos'][i]['large']['url']
                pic_list.append(pic_url)
        return pic_list

    @staticmethod
    def _get_videos(weibo_info: dict) -> list:
        video_url_list = []
        if weibo_info.get('page_info'):
            if ((weibo_info['page_info'].get('urls')
                 or weibo_info['page_info'].get('media_info'))
                    and (weibo_info['page_info'].get('type') == 'video'
                         or weibo_info['page_info'].get('object_type') == 'video')):
                media_info = weibo_info['page_info']['urls'] if weibo_info['page_info'].get('urls') else ''
                if not media_info:
                    media_info = weibo_info['page_info']['media_info']
                video_url = media_info.get('mp4_720p_mp4')
                if not video_url:
                    video_url = media_info.get('mp4_hd_url')
                if not video_url:
                    video_url = media_info.get('hevc_mp4_hd')
                if not video_url:
                    video_url = media_info.get('mp4_sd_url')
                if not video_url:
                    video_url = media_info.get('mp4_ld_mp4')
                if not video_url:
                    video_url = media_info.get('stream_url_hd')
                if not video_url:
                    video_url = media_info.get('stream_url')
                video_url_list.append(video_url)
        if weibo_info.get('mix_media_info'):
            for items in weibo_info['mix_media_info']['items']:
                if items.get('type') == 'video':
                    video_url = items.get('stream_url_hd')
                    if not video_url:
                        video_url = items['data']['media_info'].get('mp4_720p_mp4')
                    if not video_url:
                        video_url = items['data']['media_info'].get('mp4_hd_url')
                    if not video_url:
                        video_url = items['data']['media_info'].get('hevc_mp4_hd')
                    if not video_url:
                        video_url = items['data']['media_info'].get('mp4_sd_url')
                    if not video_url:
                        video_url = items['data']['media_info'].get('mp4_ld_mp4')
                    if not video_url:
                        video_url = items['data']['media_info'].get('stream_url_hd')
                    if not video_url:
                        video_url = items['data']['media_info'].get('stream_url')
                    video_url_list.append(video_url)
        return video_url_list

    @staticmethod
    def _string_to_int(string: str) -> int:
        """
        Convert Chinese numeric string to int
        :param string: str
        :return: int: int value of the string
        """
        if isinstance(string, int):
            return string
        elif string.endswith(u'万+'):
            string = string[:-2] + '0000'
        elif string.endswith(u'万'):
            string = float(string[:-1]) * 10000
        elif string.endswith(u'亿'):
            string = float(string[:-1]) * 100000000
        return int(string)

    @staticmethod
    def _get_live_photo(weibo_info: dict) -> list:
        live_photo_list = []
        live_photo = weibo_info.get('pic_video')
        if live_photo:
            prefix = 'https://video.weibo.com/media/play?livephoto=//us.sinaimg.cn/'
            for i in live_photo.split(','):
                if len(i.split(':')) == 2:
                    url = prefix + i.split(':')[1] + '.mov'
                    live_photo_list.append(url)
            return live_photo_list

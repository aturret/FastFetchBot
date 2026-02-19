import asyncio
from typing import Any, Optional

import httpx
from urllib.parse import urlparse, parse_qs

from fastfetchbot_shared.models.metadata_item import MetadataItem, MessageType, MediaFile
from src.services.file_export.audio_transcribe import AudioTranscribe
from src.services.celery_client import celery_app
from src.config import DOWNLOAD_VIDEO_TIMEOUT
from fastfetchbot_shared.utils.parse import unix_timestamp_to_utc, second_to_time, wrap_text_into_html
from fastfetchbot_shared.utils.logger import logger
from src.config import JINJA2_ENV

video_info_template = JINJA2_ENV.get_template("video_info.jinja2")


class VideoDownloader(MetadataItem):
    def __init__(
            self,
            url: str,
            category: str,
            data: Optional[Any] = None,
            download: bool = True,
            audio_only: bool = False,
            hd: bool = False,
            transcribe: bool = False,
            **kwargs,
    ):
        self.extractor = category
        self.url = url
        self.author_url = ""
        self.download = download
        self.audio_only = audio_only
        self.transcribe = transcribe
        self.hd = hd
        self.message_type = MessageType.SHORT
        self.file_path = None
        # metadata variables
        self.category = category
        self.media_files = []
        # auxiliary variables
        self.created = None
        self.duration = None

    @classmethod
    async def create(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        instance.url = await instance._parse_url(instance.url)
        return instance

    async def get_item(self) -> dict:
        self.url = await self._parse_url(self.url)
        await self.get_video()
        return self.to_dict()

    async def get_video(self) -> None:
        content_info = await self.get_video_info()
        self.file_path = content_info["file_path"]
        video_info_funcs = {
            "youtube": self._youtube_info_parse,
            "bilibili": self._bilibili_info_parse,
        }
        meta_info = video_info_funcs[self.extractor](content_info)
        self._video_info_formatting(meta_info)
        # AI transcribe
        if self.transcribe:
            audio_content_info = await self.get_video_info(audio_only=True)
            audio_file_path = audio_content_info["file_path"]
            audio_transcribe = AudioTranscribe(audio_file_path)
            transcribe_text = await audio_transcribe.transcribe()
            if self.download is False:
                self.message_type = MessageType.LONG
            self.text += "\nAI全文摘录：" + transcribe_text
            self.content += "<hr>" + wrap_text_into_html(transcribe_text)

    async def _parse_url(self, url: str) -> str:
        async def _get_redirected_url(original_url: str) -> str:
            async with httpx.AsyncClient(follow_redirects=False) as client:
                resp = await client.get(original_url)
                if resp.status_code == 200:
                    original_url = resp.url
                elif resp.status_code == 302:
                    original_url = resp.headers["Location"]
                return original_url

        def _remove_youtube_link_tracing(original_url: str) -> str:
            original_url_parser = urlparse(original_url)
            original_url_hostname = str(original_url_parser.hostname)

            if "youtu.be" in original_url_hostname:
                # remove all queries
                original_url = original_url.split("?")[0]
            if "youtube.com" in original_url_hostname:
                # remove all queries except "?v=" part
                original_url = original_url_parser.scheme + "://" + original_url_parser.netloc + original_url_parser.path
                if original_url_parser.query:
                    v_part_query = [item for item in original_url_parser.query.split("&") if "v=" in item]
                    if v_part_query:
                        original_url += "?" + v_part_query[0]
            return original_url

        def _remove_bilibili_link_tracing(original_url: str) -> str:
            original_url_parser = urlparse(original_url)
            original_url_hostname = str(original_url_parser.hostname)
            query_dict = parse_qs(original_url_parser.query)
            bilibili_p_query_string = "?p=" + query_dict["p"][0] if 'p' in query_dict else ""

            if "bilibili.com" in original_url_hostname:
                original_url = original_url_parser.scheme + "://" + original_url_parser.netloc + original_url_parser.path
            return original_url + bilibili_p_query_string

        logger.info(f"parsing original video url: {url} for {self.extractor}")

        url_parser = urlparse(url)
        url_hostname = str(url_parser.hostname)

        if self.extractor == "bilibili":
            if "b23.tv" in url_hostname:
                url = await _get_redirected_url(url)
            if "m.bilibili.com" in url_hostname:
                url = url.replace("m.bilibili.com", "www.bilibili.com")
            url = _remove_bilibili_link_tracing(url)
        elif self.extractor == "youtube":
            if "youtu.be" in url_hostname:
                url = await _get_redirected_url(url)
            url = _remove_youtube_link_tracing(url)

        logger.info(f"parsed video url: {url} for {self.extractor}")
        return url

    async def get_video_info(
            self,
            url: str = None,
            download: bool = None,
            extractor: str = None,
            audio_only: bool = None,
            hd: bool = None,
    ) -> dict:
        """
        Submit a Celery task to download/extract video info.
        :return: video info dict
        """
        if url is None:
            url = self.url
        if download is None:
            download = self.download
        if extractor is None:
            extractor = self.extractor
        if audio_only is None:
            audio_only = self.audio_only
        if hd is None:
            hd = self.hd
        body = {
            "url": url,
            "download": download,
            "extractor": extractor,
            "audio_only": audio_only,
            "hd": hd,
        }
        logger.info(f"submitting video download task: {body}")
        if download is True:
            logger.info("video downloading... it may take a while")
            if hd is True:
                logger.info("downloading HD video, it may take longer")
            elif audio_only is True:
                logger.info("downloading audio only")
        logger.debug(f"downloading video timeout: {DOWNLOAD_VIDEO_TIMEOUT}")
        result = celery_app.send_task("file_export.video_download", kwargs=body)
        response = await asyncio.to_thread(result.get, timeout=int(DOWNLOAD_VIDEO_TIMEOUT))
        content_info = response["content_info"]
        content_info["file_path"] = response["file_path"]
        return content_info

    def _video_info_formatting(self, meta_info: dict):
        self.title = meta_info["title"]
        self.author = meta_info["author"]
        self.author_url = meta_info["author_url"]
        if len(meta_info["description"]) > 800:
            meta_info["description"] = meta_info["description"][:800] + "..."
        self.created = meta_info["upload_date"]
        self.duration = meta_info["duration"]
        self.text = video_info_template.render(
            data={
                "url": self.url,
                "title": self.title,
                "author": self.author,
                "author_url": self.author_url,
                "duration": self.duration,
                "created": self.created,
                "playback_data": meta_info["playback_data"],
                "description": meta_info["description"],
            }
        )
        self.content = self.text.replace("\n", "<br>")
        if self.download:
            media_type = "video"
            if self.audio_only:
                media_type = "audio"
            self.media_files = [MediaFile(media_type, self.file_path, "")]

    @staticmethod
    def _youtube_info_parse(video_info: dict) -> dict:
        return {
            "id": video_info["id"],
            "title": video_info["title"],
            "author": video_info["uploader"],
            "author_url": video_info["uploader_url"] or video_info["channel_url"],
            "description": video_info["description"],
            "playback_data": f"视频播放量：{video_info['view_count']} 评论数：{video_info['comment_count']}",
            "author_avatar": video_info["thumbnail"],
            "upload_date": str(video_info["upload_date"]),
            "duration": second_to_time(round(video_info["duration"])),
        }

    @staticmethod
    def _bilibili_info_parse(video_info: dict) -> dict:
        return {
            "id": video_info["id"],
            "title": video_info["title"],
            "author": video_info["uploader"],
            "author_url": "https://space.bilibili.com/"
                          + str(video_info["uploader_id"]),
            "author_avatar": video_info["thumbnail"],
            "ext": video_info["ext"],
            "description": video_info["description"],
            "playback_data": f"视频播放量：{video_info['view_count']} 弹幕数：{video_info['comment_count']} 点赞数：{video_info['like_count']}",
            "upload_date": unix_timestamp_to_utc(video_info["timestamp"]),
            "duration": second_to_time(round(video_info["duration"])),
        }

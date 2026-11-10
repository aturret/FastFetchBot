"""MetadataItem for Bilibili status posts: 动态 incl. opus 图文 (source `bilibili_status`)."""

import html as html_lib
from typing import Any

from fastfetchbot_shared.exceptions import ScraperError
from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType, MetadataItem
from fastfetchbot_shared.services.scrapers.config import JINJA2_ENV
from fastfetchbot_shared.utils import bilibili as bili_utils
from fastfetchbot_shared.utils.parse import (
    get_html_text_length,
    unix_timestamp_to_utc,
    wrap_text_into_html,
)
from .dynamic import fetch_dynamic_item, parse_dynamic_item

short_text_template = JINJA2_ENV.get_template("bilibili_status_short_text.jinja2")
content_template = JINJA2_ENV.get_template("bilibili_status_content.jinja2")

LONG_TEXT_THRESHOLD = 500


class BilibiliStatus(MetadataItem):
    def __init__(self, url: str, data: Any = None, **kwargs):
        self.url = url
        self.id = None
        self.media_files = []
        self.category = "bilibili_status"
        self.message_type = MessageType.SHORT
        self.title = ""
        self.author = ""
        self.author_url = ""
        self.raw_content = ""
        self.created = None
        self.timestamp = None
        self.comment_count = None
        self.forward_count = None
        self.like_count = None

    async def get_item(self) -> dict:
        dynamic_id = await self._resolve_dynamic_id(self.url)
        item = await fetch_dynamic_item(dynamic_id)
        self._process(parse_dynamic_item(item), dynamic_id)
        return self.to_dict()

    @staticmethod
    async def _resolve_dynamic_id(url: str) -> str:
        if bili_utils.is_short_link(url):
            try:
                url = await bili_utils.expand_short_link(url)
            except Exception as e:
                raise ScraperError(f"B 站短链展开失败：{type(e).__name__}") from e
        dynamic_id = bili_utils.extract_dynamic_id(url)
        if not dynamic_id:
            raise ScraperError(f"不是 B 站动态链接：{url}")
        return dynamic_id

    def _process(self, dyn: dict, dynamic_id: str) -> None:
        self.id = dyn["id"] or dynamic_id
        self.url = f"https://t.bilibili.com/{self.id}"
        self.author = dyn["author"]
        self.author_url = f"https://space.bilibili.com/{dyn['author_mid']}" if dyn["author_mid"] else ""
        self.title = dyn["title"] or (f"{self.author}的B站动态" if self.author else "B站动态")
        self.timestamp = dyn["timestamp"]
        self.created = unix_timestamp_to_utc(self.timestamp) if self.timestamp else None
        self.comment_count = dyn["stats"]["comment"]
        self.forward_count = dyn["stats"]["forward"]
        self.like_count = dyn["stats"]["like"]

        self.raw_content = _plain_text(dyn)
        self.media_files = _media_files(dyn)
        if dyn["orig"]:
            self.media_files += _media_files(dyn["orig"])

        data = self.__dict__
        self.text = short_text_template.render(data=data)
        if get_html_text_length(self.text) > LONG_TEXT_THRESHOLD:
            self.message_type = MessageType.LONG
        html = _html_body(dyn)
        for media_file in self.media_files:
            if media_file.media_type == "image":
                html += f'<p><img src="{_e(media_file.url)}" alt=""/></p>'
            elif media_file.media_type == "video":
                html += f'<p><video src="{_e(media_file.url)}" controls="controls"></video></p>'
        self.content = content_template.render(data={**data, "html_body": html})


def _plain_text(dyn: dict) -> str:
    parts = [dyn["text"]]
    if dyn["link"]:
        parts.append(dyn["link"])
    orig = dyn["orig"]
    if orig:
        quoted = "\n".join(p for p in (orig["title"], orig["text"], orig["link"]) if p)
        parts.append(f"// @{orig['author']}：{quoted}" if quoted else f"// @{orig['author']}")
    return "\n\n".join(p for p in parts if p)


def _e(value) -> str:
    """Escape a user-supplied value for HTML text or a quoted attribute."""
    return html_lib.escape(str(value), quote=True)


def _html_body(dyn: dict) -> str:
    html = wrap_text_into_html(_e(dyn["text"])) if dyn["text"] else ""
    if dyn["link"]:
        html += f'<p><a href="{_e(dyn["link"])}">{_e(dyn["title"] or dyn["link"])}</a></p>'
    orig = dyn["orig"]
    if orig:
        author_link = (
            f'<a href="https://space.bilibili.com/{_e(orig["author_mid"])}">@{_e(orig["author"])}</a>'
            if orig["author_mid"] else f"@{_e(orig['author'])}"
        )
        quote = f"<p>{author_link}：</p>"
        if orig["title"]:
            quote += f"<p><b>{_e(orig['title'])}</b></p>"
        if orig["text"]:
            quote += wrap_text_into_html(_e(orig["text"]))
        if orig["link"]:
            quote += f'<p><a href="{_e(orig["link"])}">{_e(orig["link"])}</a></p>'
        html += f"<blockquote>{quote}</blockquote>"
    return html


def _media_files(dyn: dict) -> list[MediaFile]:
    files: list[MediaFile] = []
    for image in dyn["images"]:
        size = {"width": image["width"] or None, "height": image["height"] or None}
        files.append(MediaFile(url=image["url"], media_type="image", **size))
        if image["live_url"]:
            files.append(MediaFile(url=image["live_url"], media_type="video", **size))
    return files

import re
from typing import Dict, Optional, Any
from enum import Enum
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from lxml import etree

from app.utils.parse import get_html_text_length
from app.utils.network import get_selector
from app.utils.config import CHROME_USER_AGENT, HEADERS
from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.config import JINJA2_ENV

SHORT_LIMIT = 600

short_text_template = JINJA2_ENV.get_template("douban_short_text.jinja2")
content_template = JINJA2_ENV.get_template("douban_content.jinja2")


class DoubanType(str, Enum):
    MOVIE_REVIEW = "movie_review"
    BOOK_REVIEW = "book_review"
    NOTE = "note"
    STATUS = "status"
    GROUP = "group"
    UNKNOWN = "unknown"


class Douban(MetadataItem):
    item_title: Optional[str]
    item_url: Optional[str]
    group_name: Optional[str]
    group_url: Optional[str]
    douban_type: DoubanType
    text_group: Optional[str]
    raw_content: Optional[str]
    date: Optional[str]

    def __init__(self, url: str, data: Any, **kwargs):
        # metadata fields
        self.url = url
        self.title = ""
        self.author = ""
        self.author_url = ""
        self.text = ""
        self.content = ""
        self.media_files = []
        self.category = "douban"
        self.message_type = MessageType.SHORT
        # auxiliary fields
        self.item_title: Optional[str] = None
        self.item_url: Optional[str] = None
        self.group_name: Optional[str] = None
        self.group_url: Optional[str] = None
        self.douban_type: DoubanType = DoubanType.UNKNOWN
        self.text_group: Optional[str] = None
        self.raw_content: Optional[str] = None
        self.date: Optional[str] = None
        # reqeust fields
        self.headers = HEADERS
        self.headers["Cookie"] = kwargs.get("cookie", "")

    async def get_item(self) -> dict:
        await self.get_douban()
        return self.to_dict()

    async def get_douban(self) -> None:
        self.check_douban_type()
        await self.get_douban_item()

    def check_douban_type(self):
        urlparser = urlparse(self.url)
        host = urlparser.netloc
        path = urlparser.path
        if host.find("m.douban") != -1:  # parse the m.douban url
            host = host.replace("m.douban", "douban")
            if path.startswith("/movie/review"):
                self.douban_type = DoubanType.MOVIE_REVIEW
                host = host.replace("douban", "movie.douban")
                path = path.replace("/movie/", "/")
            elif path.startswith("/book/review"):
                self.douban_type = DoubanType.BOOK_REVIEW
                host = host.replace("douban", "book.douban")
                path = path.replace("/book/", "/")
        if path.startswith("/note/"):
            self.douban_type = DoubanType.NOTE
        elif path.startswith("/status/"):
            self.douban_type = DoubanType.STATUS
        elif path.startswith("/group/topic/"):
            self.douban_type = DoubanType.GROUP
        elif host.startswith("movie.douban") and path.startswith("/review/"):
            self.douban_type = DoubanType.MOVIE_REVIEW
        elif host.startswith("book.douban") and path.startswith("/review/"):
            self.douban_type = DoubanType.BOOK_REVIEW
        else:
            self.douban_type = DoubanType.UNKNOWN
        self.url = f"https://{host}{path}"

    async def get_douban_item(self):
        function_dict = {
            DoubanType.MOVIE_REVIEW: self._get_douban_movie_review,
            DoubanType.BOOK_REVIEW: self._get_douban_book_review,
            DoubanType.NOTE: self._get_douban_note,
            DoubanType.STATUS: self._get_douban_status,
            DoubanType.GROUP: self._get_douban_group_article,
            DoubanType.UNKNOWN: None,
        }
        await function_dict[self.douban_type]()
        data = self.__dict__
        self.text = short_text_template.render(data=data)
        self.content = content_template.render(data=data)
        self._douban_short_text_process()
        if get_html_text_length(self.content) > SHORT_LIMIT:
            self.message_type = MessageType.LONG
        else:
            self.message_type = MessageType.SHORT

    async def _get_douban_movie_review(self):
        selector = await get_selector(url=self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1//span)')
        self.author = selector.xpath('string(//header[@class="main-hd"]//span)')
        self.author_url = selector.xpath('string(//header[@class="main-hd"]/a/@href)')
        self.item_title = selector.xpath('string(//header[@class="main-hd"]/a[2])')
        self.item_url = selector.xpath('string(//header[@class="main-hd"]/a[2]/@href)')
        self.raw_content = str(
            etree.tostring(
                selector.xpath("//div[contains(@class,'review-content')]")[0],
                encoding="utf-8",
            ),
            encoding="utf-8",
        )

    async def _get_douban_book_review(self):
        selector = await get_selector(self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1//span)')
        self.author = selector.xpath('string(//header[@class="main-hd"]//span)')
        self.author_url = selector.xpath('string(//header[@class="main-hd"]/a/@href)')
        self.item_title = selector.xpath('string(//header[@class="main-hd"]/a[2])')
        self.item_url = selector.xpath('string(//header[@class="main-hd"]/a[2]/@href)')
        self.raw_content = str(
            etree.tostring(
                selector.xpath('//div[@id="link-report"]')[0], encoding="utf-8"
            ),
            encoding="utf-8",
        )

    async def _get_douban_note(self):
        selector = await get_selector(self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1)')
        self.author = selector.xpath('string(//div[@class="content"]/a)')
        self.author_url = selector.xpath('string(//div[@class="content"]/a/@href)')
        self.raw_content = str(
            etree.tostring(
                selector.xpath('//div[@id="link-report"]')[0], encoding="utf-8"
            ),
            encoding="utf-8",
        )

    async def _get_douban_status(self):
        selector = await get_selector(self.url, headers=self.headers)
        self.author = selector.xpath('string(//div[@class="content"]/a)')
        self.author_url = selector.xpath('string(//div[@class="content"]/a/@href)')
        self.title = self.author + "的广播"
        self.raw_content = (
            str(
                etree.tostring(
                    selector.xpath('//div[@class="status-saying"]')[0], encoding="utf-8"
                ),
                encoding="utf-8",
            )
            .replace("<blockquote>", "")
            .replace("</blockquote>", "")
            .replace(">+<", "><")
            .replace("&#13;", "<br>")
        )

    async def _get_douban_group_article(self):
        selector = await get_selector(self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1)')
        self.title = self.title.replace("\n", "").strip()
        self.author = selector.xpath('string(//span[@class="from"]//a)')
        self.author_url = selector.xpath('string(//span[@class="from"]//a/@href)')
        self.group_name = selector.xpath(
            'string(//div[@id="g-side-info"]//div[@class="title"]/a)'
        )
        self.group_url = selector.xpath(
            'string(//div[@id="g-side-info"]//div[@class="title"]/a/@href)'
        )
        self.raw_content = str(
            etree.tostring(
                selector.xpath('//div[@id="link-report"]')[0], encoding="utf-8"
            ),
            encoding="utf-8",
        )

    def _douban_short_text_process(self):
        soup = BeautifulSoup(self.raw_content, "html.parser")
        for img in soup.find_all("img"):
            media_item = {"media_type": "image", "url": img["src"], "caption": ""}
            self.media_files.append(MediaFile.from_dict(media_item))
            img.extract()
        for item in soup.find_all(["p", "span", "div"]):
            item.unwrap()
        for item in soup.find_all(["link", "script"]):
            item.decompose()
        self.text += str(soup)
        self.text = re.sub(r"\n{2,}", "\n", self.text)
        self.text = re.sub(r"<br\s*/?>", "\n", self.text)

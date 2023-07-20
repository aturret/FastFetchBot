import re
from typing import Dict, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from lxml import etree

from app.utils.parse import get_html_text_length
from app.utils.network import get_selector
from app.utils.config import CHROME_USER_AGENT, HEADERS
from app.models.metadata_item import MetadataItem, MediaFile


class Douban(MetadataItem):
    def __init__(self, url: str, **kwargs):
        # metadata fields
        self.url = url
        self.title = ""
        self.author = ""
        self.author_url = ""
        self.text = ""
        self.content = ""
        self.media_files = []
        self.category = "douban"
        self.type = "short"
        # auxiliary fields
        self.item_title = ""
        self.item_url = ""
        self.group_name = ""
        self.group_url = ""
        self.douban_type = ""
        self.text_group = ""
        self.content_group = ""
        self.date = ""
        # reqeust fields
        self.headers = HEADERS
        self.headers["Cookie"] = kwargs.get("cookie", "")

    async def get_douban(self) -> Dict:
        self.check_douban_type()
        await self.get_douban_item()
        return self.to_dict()

    def check_douban_type(self):
        urlparser = urlparse(self.url)
        host = urlparser.netloc
        path = urlparser.path
        if "m.douban" in host:  # parse the m.douban url
            host = host.replace("m.douban", "douban")
            if path.startswith("/movie/review"):
                self.douban_type = "movie"
                host = host.replace("douban", "movie.douban")
                path = path.replace("/movie/", "/")
            elif path.startswith("/book/review"):
                self.douban_type = "book"
                host = host.replace("douban", "book.douban")
                path = path.replace("/book/", "/")
        if path.startswith("/note/"):
            self.douban_type = "note"
        elif path.startswith("/status/"):
            self.douban_type = "status"
        elif path.startswith("/group/topic/"):
            self.douban_type = "group"
        elif host.startswith("movie.douban") and path.startswith("/review/"):
            self.douban_type = "movie"
        elif host.startswith("book.douban") and path.startswith("/review/"):
            self.douban_type = "book"
        else:
            self.douban_type = "unknown"
        self.url = f"https://{host}{path}"

    async def get_douban_item(self):
        function_dict = {
            "movie": self.get_douban_movie_review,
            "book": self.get_douban_book_review,
            "note": self.get_douban_note,
            "status": self.get_douban_status,
            "group": self.get_douban_group_article,
            "unknown": None
        }
        await function_dict[self.douban_type]()
        self.douban_short_text_process()

    async def get_douban_movie_review(self):
        selector = await get_selector(url=self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1//span)')
        self.content = str(
            etree.tostring(selector.xpath('//div[contains(@class,\'review-content\')]')[0], encoding="utf-8"),
            encoding='utf-8')
        self.author = selector.xpath('string(//header[@class="main-hd"]//span)')
        self.author_url = selector.xpath('string(//header[@class="main-hd"]/a/@href)')
        self.item_title = selector.xpath('string(//header[@class="main-hd"]/a[2])')
        self.item_url = selector.xpath('string(//header[@class="main-hd"]/a[2]/@href)')

    async def get_douban_book_review(self):
        selector = get_selector(self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1//span)')
        self.content = str(etree.tostring(selector.xpath('//div[@id="link-report"]')[0], encoding="utf-8"),
                           encoding='utf-8')
        self.author = selector.xpath('string(//header[@class="main-hd"]//span)')
        self.author_url = selector.xpath('string(//header[@class="main-hd"]/a/@href)')
        self.item_title = selector.xpath('string(//header[@class="main-hd"]/a[2])')
        self.item_url = selector.xpath('string(//header[@class="main-hd"]/a[2]/@href)')

    async def get_douban_note(self):
        selector = get_selector(self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1)')
        self.content = str(etree.tostring(selector.xpath('//div[@id="link-report"]')[0], encoding="utf-8"),
                           encoding='utf-8')
        self.author = selector.xpath('string(//div[@class="content"]/a)')
        self.author_url = selector.xpath('string(//div[@class="content"]/a/@href)')
        pass

    async def get_douban_status(self):
        selector = get_selector(self.url, headers=self.headers)
        self.content = str(etree.tostring(selector.xpath('//div[@class="status-saying"]')[0], encoding="utf-8"),
                           encoding='utf-8').replace('<blockquote>', '').replace('</blockquote>', '').replace('>+<',
                                                                                                              '><').replace(
            '&#13;', '<br>')
        self.author = selector.xpath('string(//div[@class="content"]/a)')
        self.author_url = selector.xpath('string(//div[@class="content"]/a/@href)')
        self.title = self.author + '的广播'

    async def get_douban_group_article(self):
        selector = get_selector(self.url, headers=self.headers)
        self.title = selector.xpath('string(//div[@id="content"]//h1)')
        self.title = self.title.replace('\n', '').strip()
        self.author = selector.xpath('string(//span[@class="from"]//a)')
        self.author_url = selector.xpath('string(//span[@class="from"]//a/@href)')
        self.group_name = selector.xpath('string(//div[@id="g-side-info"]//div[@class="title"]/a)')
        self.group_url = selector.xpath('string(//div[@id="g-side-info"]//div[@class="title"]/a/@href)')
        self.content = (
            f"<p>作者：<a href=\"{self.author_url}\">{self.author}</p>"
            f"<p>来自<a href=\"{self.group_url}\">{self.group_name}</p>" +
            str(etree.tostring(selector.xpath('//div[@id="link-report"]')[0], encoding="utf-8"),
                           encoding='utf-8'))

    def douban_short_text_process(self):
        # TODO: customize the process of short text for each douban type.
        soup = BeautifulSoup(self.content, 'html.parser')
        self.media_files = []
        for img in soup.find_all('img'):
            media_item = {'media_type': 'image', 'url': img['src'], 'caption': ''}
            self.media_files.append(MediaFile.from_dict(media_item))
            img.extract()
        for p in soup.find_all('p'):
            p.unwrap()
        for span in soup.find_all('span'):
            span.unwrap()
        for div in soup.find_all('div'):
            div.unwrap()
        for link in soup.find_all('link'):
            link.decompose()
        for script in soup.find_all('script'):
            script.decompose()
        self.text = str(soup)
        while '\n\n' in self.text:
            self.text = self.text.replace('\n\n', '\n')
        self.text = self.text.replace('<br/>', '\n').replace('<br>', '\n').replace('<br />', '\n')
        self.text = '<a href="' + self.url + '">' + self.author + '</a>: ' + self.text


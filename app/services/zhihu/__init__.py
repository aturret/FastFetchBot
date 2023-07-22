import re
from lxml import html
from typing import Dict, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from lxml import etree

from app.utils.parse import (
    get_html_text_length,
    format_telegram_short_text,
    unix_timestamp_to_utc,
)
from app.utils.network import get_selector, get_response_json
from app.utils.config import CHROME_USER_AGENT, HEADERS
from app.models.metadata_item import MetadataItem, MediaFile


SHORT_LIMIT = 600
ZHIHU_COLUMNS_API_HOST = 'https://zhuanlan.zhihu.com/api'
ZHIHU_API_HOST = 'https://www.zhihu.com/api/v4'
ZHIHU_HOST = 'https://www.zhihu.com'

class Zhihu(MetadataItem):
    def __init__(self, url: str, **kwargs):
        # metadata fields
        self.url = url
        self.title = ""
        self.author = ""
        self.author_url = ""
        self.text = ""
        self.content = ""
        self.media_files: list[MediaFile] = []
        self.category = "zhihu"
        self.type = "short"
        # auxiliary fields
        self.item_title = ""
        self.item_url = ""
        self.group_name = ""
        self.group_url = ""
        self.zhihu_type = ""
        self.text_group = ""
        self.raw_content = ""
        self.date = ""
        # reqeust fields
        self.headers = HEADERS
        self.headers["Cookie"] = kwargs.get("cookie", "")
        self.method = kwargs.get("method", "api")
        self.urlparser = urlparse(self.url)
        self.api_url = ""

    async def get_zhihu(self) -> Dict:
        self.check_zhihu_type()
        await self.get_zhihu_item()
        return self.to_dict()

    def check_zhihu_type(self):
        urlparser = urlparse(self.url)
        host = urlparser.netloc
        path = urlparser.path
        # if "m.zhihu" in host:  # parse the m.zhihu url
        #     host = host.replace("m.zhihu", "zhihu")
        #     if path.startswith("/movie/review"):
        #         self.zhihu_type = "movie"
        #         host = host.replace("zhihu", "movie.zhihu")
        #         path = path.replace("/movie/", "/")
        #     elif path.startswith("/book/review"):
        #         self.zhihu_type = "book"
        #         host = host.replace("zhihu", "book.zhihu")
        #         path = path.replace("/book/", "/")
        if host.startswith("zhuanlan."):
            self.zhihu_type = "article"
        elif path.find("answer") != -1:
            self.zhihu_type = "answer"
        elif path.startswith("/pin/"):
            self.zhihu_type = "status"
        else:
            self.zhihu_type = "unknown"
        self.url = f"https://{host}{path}"

    async def get_zhihu_item(self):
        function_dict = {
            "movie": self.get_zhihu_movie_review,
            "book": self.get_zhihu_book_review,
            "note": self.get_zhihu_note,
            "status": self.get_zhihu_status,
            "group": self.get_zhihu_group_article,
            "unknown": None,
        }
        await function_dict[self.zhihu_type]()
        self.zhihu_short_text_process()
        if get_html_text_length(self.content) > SHORT_LIMIT:
            self.type = "long"
        else:
            self.type = "short"

    async def get_zhihu_answer(self):
        selector = await get_selector(self.url, headers=self.headers)
        upvote = selector.xpath('string(//button[contains(@class,"VoteButton")])')
        self.raw_content = str(
            etree.tostring(
                selector.xpath(
                    '//div[contains(@class,"RichContent-inner")]//span[contains(@class,"RichText") and @itemprop="text"]'
                )[0],
                encoding="utf-8",
            ),
            encoding="utf-8",
        )
        self.title = selector.xpath("string(//h1)")
        self.author = selector.xpath(
            'string(//div[@class="AuthorInfo"]//meta[@itemprop="name"]/@content)'
        )
        self.author_url = selector.xpath(
            'string(//div[@class="AuthorInfo"]//meta[@itemprop="url"]/@content)'
        )
        if self.author_url == "https://www.zhihu.com/people/":
            self.author_url = ""
        self.content = "<p>" + upvote + "</p><br>" + self.raw_content
        self.text = (
            f'<a href="{self.author}">{self.author_url}</a>的豆瓣日记： \n'
            f'<a href="{self.url}"><b>{self.title}</b></a>\n'
        )
        self.content = self.text.replace("\n", "<br>") + self.raw_content

    async def get_zhihu_status(self):
        selector = await get_selector(self.url, headers=self.headers)
        self.zhihu_type = "status"
        if self.method == "api":
            self.api_url = (
                "https://www.zhihu.com/api/v4/pins/"
                + re.findall(r"pin/(\d+)\D*", self.url)[0]
            )
            print(self.api_url)
            json_data = await get_response_json(
                self.api_url, headers=self.headers, test=True
            )
            # json_data = await get_zhihu_json_data(self.api_url, headers=self.headers)
            self.author = json_data["author"]["name"]
            self.author_url = ZHIHU_HOST + "/people/" + json_data["author"]["url_token"]
            self.title = self.author + "的想法"
            self.content = json_data["content_html"]
            self.get_zhihu_short_text()
            self.created = unix_timestamp_to_utc(json_data["created"])
            self.updated = unix_timestamp_to_utc(json_data["updated"])
            timestamp = (
                "修改于：" + self.updated
                if json_data["updated"] > json_data["created"]
                else "发布于：" + self.created
            )
            upvote = json_data["like_count"]
            self.content = (
                "点赞数："
                + str(upvote)
                + "<br>"
                + self.content
                + "<br>"
                + self.retweet_html
                + "<br>"
                + timestamp
            )
        elif self.method == "html":
            selector = get_selector(url=self.url, headers=self.headers)
            content = str(
                etree.tostring(
                    selector.xpath(
                        '//span[contains(@class,"RichText") and @itemprop="text"]'
                    )[0],
                    encoding="utf-8",
                ),
                encoding="utf-8",
            )
            upvote = selector.xpath(
                'string(//button[contains(@class,"VoteButton")]//span)'
            )
            timestamp = selector.xpath('string(//div[@class="ContentItem-time"]//span)')
            if (
                selector.xpath(
                    'string(//div[@class="RichContent"]/div[2]/div[2]/@class)'
                ).find("PinItem-content-originpin")
                != -1
            ):  # 是否存在转发
                if (
                    str(
                        etree.tostring(
                            selector.xpath(
                                '//div[contains(@class,"PinItem-content-originpin")]/div[3]'
                            )[0],
                            encoding="utf-8",
                        ),
                        encoding="utf-8",
                    )
                    != '<div class="RichText ztext PinItem-remainContentRichText"/>'
                ):  # 如果转发内容有图
                    pichtml = html.fromstring(
                        str(
                            etree.tostring(
                                selector.xpath(
                                    '//div[contains(@class,"PinItem-content-originpin")]'
                                )[0],
                                encoding="utf-8",
                            ),
                            encoding="utf-8",
                        )
                    )
                    self.retweet_html = str(
                        html.tostring(pichtml, pretty_print=True)
                    ).replace("b'<div", "<div")
                    print(type(self.retweet_html))
                    print(self.retweet_html)
                else:
                    self.retweet_html = str(
                        etree.tostring(
                            selector.xpath(
                                '//div[contains(@class,"PinItem-content-originpin")]'
                            )[0],
                            encoding="utf-8",
                        ),
                        encoding="utf-8",
                    )
                    print(self.retweet_html)
            self.content = (
                "点赞数："
                + upvote
                + "<br>"
                + content
                + "<br>"
                + self.retweet_html
                + "<br>"
                + timestamp
            )
            self.author = selector.xpath(
                'string(//div[@class="AuthorInfo"]//meta[@itemprop="name"]/@content)'
            )
            self.author_url = selector.xpath(
                'string(//div[@class="AuthorInfo"]//meta[@itemprop="url"]/@content)'
            )
            self.title = self.author + "的想法"
        self.text = f'<a href="{self.url}"><b>{self.title}</b></a>：\n'
        self.content = self.text.replace("\n", "<br>") + self.raw_content

    async def get_zhihu_article(self):
        self.zhihu_type = "article"
        if self.method == "api":
            self.api_url = (
                ZHIHU_COLUMNS_API_HOST
                + "/articles/"
                + re.findall(r"/p/(\d+)\D*", self.url)[0]
            )
            json_data = await get_response_json(self.api_url, headers=self.headers)
            self.title = json_data["title"]
            self.content = json_data["content"]
            self.author = json_data["author"]["name"]
            self.author_url = ZHIHU_HOST + "/people/" + json_data["author"]["url_token"]
            upvote = json_data["voteup_count"]
            self.get_zhihu_short_text()
        elif self.method == "html":
            self.zhihu_type = "article"
            selector = get_selector(url=self.url, headers=self.headers)
            self.title = selector.xpath("string(//h1)")
            upvote = selector.xpath(
                'string(//button[@class="Button VoteButton VoteButton--up"])'
            )
            self.content = str(
                etree.tostring(
                    selector.xpath(
                        '//div[contains(@class,"RichText") and contains(@class,"ztext")]'
                    )[0],
                    encoding="utf-8",
                ),
                encoding="utf-8",
            )
            self.get_zhihu_short_text()
            self.content = upvote + "<br>" + self.content
            self.author = selector.xpath(
                'string(//div[contains(@class,"AuthorInfo-head")]//a)'
            )
            self.author_url = "https:" + selector.xpath(
                'string(//a[@class="UserLink-link"]/@href)'
            )
        self.text = (
            f'<a href="{self.group_url}">{self.group_name}</a>： \n'
            f'<a href="{self.url}"><b>{self.title}</b></a>\n'
        )
        self.content = (
            f'<p>作者：<a href="{self.author_url}">{self.author}</p>'
            f'<p>来自<a href="{self.group_url}">{self.group_name}</p>' + self.raw_content
        )

    def zhihu_short_text_process(self):
        soup = BeautifulSoup(self.content, "html.parser")
        for img in soup.find_all("img"):
            if img["src"].find("data:image") != -1:
                continue
            media_item = MediaFile.from_dict(
                {"media_type": "image", "url": img["src"], "caption": ""}
            )
            self.media_files.append(media_item)
            img.decompose()
        for figure in soup.find_all("figure"):
            figure.append(BeautifulSoup("<br>", "html.parser"))
            figure.decompose()
        print(self.content)
        if self.zhihu_type == "status":
            self.text = (
                '<a href="'
                + self.aurl
                + '"><b>'
                + self.title
                + "</b>"
                + "</a>："
                + str(soup)
            )
        else:
            self.text = (
                '<a href="'
                + self.aurl
                + '"><b>'
                + self.title
                + "</b> - "
                + self.author
                + "的"
                + zhihu_type_translate[self.zhihu_type]
                + "</a>：\n"
                + str(soup)
            )
        soup = BeautifulSoup(self.text, "html.parser")
        soup = format_telegram_short_text(soup)
        for p in soup.find_all("p"):
            if p.text != "":
                p.append(BeautifulSoup("<br>", "html.parser"))
            p.unwrap()
        self.text = (
            str(soup)
            .replace("<br/>", "\n")
            .replace("<br>", "\n")
            .replace("<br />", "")
            .replace("<hr/>", "\n")
        )

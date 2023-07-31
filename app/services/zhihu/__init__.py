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
from app.models.metadata_item import MetadataItem, MediaFile
from app.utils.config import CHROME_USER_AGENT, HEADERS
from app.config import JINJA2_ENV
from .config import (
    SHORT_LIMIT,
    ZHIHU_COLUMNS_API_HOST,
    ZHIHU_API_HOST,
    ZHIHU_HOST,
    ALL_METHODS,
)

environment = JINJA2_ENV
short_text_template = environment.get_template("zhihu_short_text.jinja2")
content_template = environment.get_template("zhihu_content.jinja2")


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
        self.updated = ""
        self.retweet_html = ""
        # reqeust fields
        self.headers = HEADERS
        self.headers["Cookie"] = kwargs.get("cookie", "")
        self.method = kwargs.get("method", "api")
        self.urlparser = urlparse(self.url)
        self.api_url = ""
        # other hard-coded fields
        self.zhihu_type_translate = {
            "article": "专栏文章",
            "answer": "回答",
            "status": "想法",
        }

    async def get_zhihu(self) -> Dict:
        """
        Main function.
        Get the zhihu item and return the metadata dict.
        :return: Dict
        """
        self._check_zhihu_type()
        await self._get_zhihu_item()
        return self.to_dict()

    def _check_zhihu_type(self) -> None:
        """
        Check the zhihu type of the url. The zhihu type can be one of the following:
        - article (example: https://zhuanlan.zhihu.com/p/35142635)
        - answer (example: https://www.zhihu.com/question/19998424/answer/603067076)
        - status (example: https://www.zhihu.com/pin/1667965059081945088)
        """
        urlparser = urlparse(self.url)
        host = urlparser.netloc
        path = urlparser.path
        if host.startswith("zhuanlan."):
            self.zhihu_type = "article"
        elif path.find("answer") != -1:
            self.zhihu_type = "answer"
        elif path.startswith("/pin/"):
            self.zhihu_type = "status"
        else:
            self.zhihu_type = "unknown"
        self.url = f"https://{host}{path}"

    async def _get_zhihu_item(self) -> None:
        """
        Get zhihu item via the corresponding method according to the zhihu type.
        """
        function_dict = {
            "answer": self._get_zhihu_answer,
            "article": self.get_zhihu_article,
            "status": self._get_zhihu_status,
            "unknown": None,
        }
        await function_dict[self.zhihu_type]()
        self.zhihu_short_text_process()
        if get_html_text_length(self.content) > SHORT_LIMIT:
            self.type = "long"
        else:
            self.type = "short"

    async def _get_zhihu_answer(self) -> None:
        """
        parse the zhihu answer page and get the metadata.
        support methods: html, json. Recommend: json
        """
        if self.method == "api":
            pass  # zhihu v4 api does not open for answer
        elif self.method == "json":
            pass
        elif self.method == "html":
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
            self.content = ("<p>" + upvote + "</p><br>" + self.raw_content).replace(
                "\n", "<br>"
            )
            self.text = (
                f'<a href="{self.author}">{self.author_url}</a>的知乎回答： \n'
                f'<a href="{self.url}"><b>{self.title}</b></a>\n'
            )

    async def _get_zhihu_status(self):
        """
        parse the zhihu status page and get the metadata.
        support methods: api, html
        """
        if self.method == "api":
            self.api_url = (
                "https://www.zhihu.com/api/v4/pins/"
                + self.urlparser.path.split("/")[-1]
            )
            print(self.api_url)
            json_data = await get_response_json(
                self.api_url, headers=self.headers, test=True
            )
            # json_data = await get_zhihu_json_data(self.api_url, headers=self.headers)
            self.author = json_data["author"]["name"]
            self.author_url = ZHIHU_HOST + "/people/" + json_data["author"]["url_token"]
            self.title = self.author + "的知乎想法"
            self.content = json_data["content_html"]
            self.zhihu_short_text_process()
            self.date = unix_timestamp_to_utc(json_data["created"])
            self.updated = unix_timestamp_to_utc(json_data["updated"])
            timestamp = (
                "修改于：" + self.updated
                if json_data["updated"] > json_data["created"]
                else "发布于：" + self.date
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
            selector = await get_selector(self.url, headers=self.headers)
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
                    pic_html = html.fromstring(
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
                        html.tostring(pic_html, pretty_print=True)
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
                + self.urlparser.path.split("/")[-1]
            )
            json_data = await get_response_json(self.api_url, headers=self.headers)
            self.title = json_data["title"]
            self.content = json_data["content"]
            self.author = json_data["author"]["name"]
            self.author_url = ZHIHU_HOST + "/people/" + json_data["author"]["url_token"]
            upvote = json_data["voteup_count"]
            self.zhihu_short_text_process()
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
            self.zhihu_short_text_process()
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
        content = str(soup)
        self.text = short_text_template.render(
            zhihu_type=self.zhihu_type,
            translated_zhihu_type=self.zhihu_type_translate[self.zhihu_type],
            title=self.title,
            author=self.author,
            author_url=self.author_url,
            url=self.url,
            content=content,
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

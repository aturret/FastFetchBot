import json
import re
import traceback
from typing import Dict, Optional
from urllib.parse import urlparse

import jmespath
from bs4 import BeautifulSoup
from lxml import etree, html

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
        self.upvote = None
        # reqeust fields
        self.headers = HEADERS
        self.headers["Cookie"] = kwargs.get("cookie", "")
        self.method = kwargs.get("method", "json")
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
        await self._get_zhihu_item()
        return self.to_dict()

    async def _get_zhihu_item(self) -> None:
        """
        Get zhihu item via the corresponding method according to the zhihu type.
        """
        self._check_zhihu_type()
        function_dict = {
            "answer": self._get_zhihu_answer,
            "article": self._get_zhihu_article,
            "status": self._get_zhihu_status,
            "unknown": None,
        }
        for method in ALL_METHODS:
            try:
                if self.method not in ALL_METHODS:
                    self.method = "json"
                else:
                    self.method = method
                await function_dict[self.zhihu_type]()
            except Exception as e:
                traceback.print_exc()
                if method == ALL_METHODS[-1]:
                    print("all methods failed")
                else:
                    print(
                        f"zhihu {self.zhihu_type} {self.method} failed, try the next method"
                    )
                continue
        self._zhihu_short_text_process()
        self._zhihu_content_process()
        self.type = (
            "long" if get_html_text_length(self.content) > SHORT_LIMIT else "short"
        )

    def _check_zhihu_type(self) -> None:
        """
        Check the zhihu type of the url. The zhihu type can be one of the following:
        - answer (example: https://www.zhihu.com/question/19998424/answer/603067076)
        - article (example: https://zhuanlan.zhihu.com/p/35142635)
        - status (example: https://www.zhihu.com/pin/1667965059081945088)
        """
        urlparser = urlparse(self.url)
        host = urlparser.netloc
        path = urlparser.path
        if host.startswith("zhuanlan."):
            self.zhihu_type = "article"
            self.article_id = self.urlparser.path.split("/")[-1]
        elif path.find("answer") != -1:
            self.zhihu_type = "answer"
            self.answer_id = self.urlparser.path.split("/")[-1]
        elif path.startswith("/pin/"):
            self.zhihu_type = "status"
            self.status_id = self.urlparser.path.split("/")[-1]
        else:
            self.zhihu_type = "unknown"
        self.url = f"https://{host}{path}"

    async def _get_zhihu_answer(self) -> None:
        """
        parse the zhihu answer page and get the metadata.
        support methods: html, json. Recommend: json
        """
        if self.method == "api":
            pass  # zhihu v4 api does not open for answer
        else:
            try:
                selector = await get_selector(self.url, headers=self.headers)
            except:
                raise Exception("Cannot get the selector")
            if self.method == "json":
                json_data = selector.xpath('string(//script[@id="js-initialData"])')
                json_data = json.loads(json_data)
                print(json.dumps(json_data, indent=4, ensure_ascii=False))
                json_data = json_data["initialState"]["entities"]
                answer_data = self._parse_answer_json_data(json_data)
                self.question_id = answer_data["question_id"]
                question_data = self._parse_question_json_data(json_data)
                self.question = question_data["question_detail"]
                self.question_date = unix_timestamp_to_utc(question_data["created"])
                self.question_updated = unix_timestamp_to_utc(question_data["updated"])
                self.question_follower_count = question_data["follower_count"]
                self.question_answer_count = question_data["answer_count"]
                self.title = question_data["title"]
                self.author = answer_data["author"]
                self.author_url = (
                    ZHIHU_HOST + "/people/" + answer_data["author_url_token"]
                )
                self.raw_content = answer_data["content"]
                self.date = unix_timestamp_to_utc(answer_data["created"])
                self.updated = unix_timestamp_to_utc(answer_data["updated"])
                self.comment_count = answer_data["comment_count"]
                self.upvote = answer_data["voteup_count"]
                self.ip_info = answer_data["ip_info"]
            elif self.method == "html":
                self.upvote = selector.xpath(
                    'string(//button[contains(@class,"VoteButton")])'
                )
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
        if (
            self.title == ""
        ):  # TODO: this is not a good way to check if the scraping is successful. To be improved.
            raise Exception("Cannot get the answer")

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
            self.title = self.author + "的想法"
            self.content = json_data["content_html"]
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
        else:
            try:
                selector = await get_selector(self.url, headers=self.headers)
            except:
                raise Exception("zhihu request failed")
            if self.method == "json":
                json_data = selector.xpath('string(//script[@id="js-initialData"])')
                json_data = json.loads(json_data)
                print(json.dumps(json_data, indent=4, ensure_ascii=False))
            elif self.method == "html":
                self.raw_content = str(
                    etree.tostring(
                        selector.xpath(
                            '//span[contains(@class,"RichText") and @itemprop="text"]'
                        )[0],
                        encoding="utf-8",
                    ),
                    encoding="utf-8",
                )
                self.upvote = selector.xpath(
                    'string(//button[contains(@class,"VoteButton")]//span)'
                )
                self.date = selector.xpath(
                    'string(//div[@class="ContentItem-time"]//span)'
                )
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
                    + self.upvote
                    + "<br>"
                    + self.raw_content
                    + "<br>"
                    + self.retweet_html
                    + "<br>"
                    + self.date
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

    async def _get_zhihu_article(self):
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
            self.upvote = json_data["voteup_count"]
        else:
            try:
                selector = await get_selector(self.url, headers=self.headers)
            except:
                raise Exception("zhihu request failed")
            if self.method == "json":
                json_data = selector.xpath('string(//script[@id="js-initialData"])')
                json_data = json.loads(json_data)
                json_data = json_data["initialState"]["entities"]
                article_data = self._parse_article_json_data(json_data)
                self.title = article_data["title"]
                self.raw_content = article_data["content"]
                self.author = article_data["author"]
                self.author_url = (
                    ZHIHU_HOST + "/people/" + article_data["author_url_token"]
                )
                self.upvote = article_data["voteup_count"]
                self.comment_count = article_data["comment_count"]
                self.date = unix_timestamp_to_utc(article_data["created"])
                self.updated = unix_timestamp_to_utc(article_data["updated"])
                self.column = article_data["column"]
                self.column_url = article_data["column_url"]
                self.column_intro = article_data["column_intro"]
            elif self.method == "html":
                self.title = selector.xpath("string(//h1)")
                self.upvote = selector.xpath(
                    'string(//button[@class="Button VoteButton VoteButton--up"])'
                )
                self.raw_content = str(
                    etree.tostring(
                        selector.xpath(
                            '//div[contains(@class,"RichText") and contains(@class,"ztext")]'
                        )[0],
                        encoding="utf-8",
                    ),
                    encoding="utf-8",
                )
                self.author = selector.xpath(
                    'string(//div[contains(@class,"AuthorInfo-head")]//a)'
                )
                self.author_url = "https:" + selector.xpath(
                    'string(//a[@class="UserLink-link"]/@href)'
                )

    def _zhihu_short_text_process(self):
        soup = BeautifulSoup(self.raw_content, "html.parser")
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

    def _zhihu_content_process(self):
        data = self.__dict__
        data["raw_content"] = data["raw_content"].replace("\n", "<br>")
        self.content = content_template.render(data=data)

    def _parse_answer_json_data(self, data: Dict) -> Dict:
        expression = f"""{{
                question_id: answers."{self.answer_id}".question.id,
                author: answers."{self.answer_id}".author.name,
                author_url_token: answers."{self.answer_id}".author.urlToken,
                content: answers."{self.answer_id}".content,
                created: answers."{self.answer_id}".createdTime
                updated: answers."{self.answer_id}".updatedTime,
                comment_count: answers."{self.answer_id}".commentCount,
                voteup_count: answers."{self.answer_id}".voteupCount,
                ip_info: answers."{self.answer_id}".ipInfo
            }}"""
        result = jmespath.search(expression, data)
        return result

    def _parse_question_json_data(self, data: Dict) -> Dict:
        expression = f"""{{
                "title": questions."{self.question_id}".title,
                "question_detail": questions."{self.question_id}".detail,
                "answer_count": questions."{self.question_id}".answerCount,
                "follower_count": questions."{self.question_id}".followerCount,
                "created": questions."{self.question_id}".created,
                "updated": questions."{self.question_id}".updatedTime
            }}"""
        result = jmespath.search(expression, data)
        return result

    def _parse_article_json_data(self, data: Dict) -> Dict:
        expression = f"""{{
            "title": articles."{self.article_id}".title,
            "content": articles."{self.article_id}".content,
            "author": articles."{self.article_id}".author.name,
            "author_url_token": articles."{self.article_id}".author.urlToken,
            "voteup_count": articles."{self.article_id}".voteupCount,
            "comment_count": articles."{self.article_id}".commentCount,
            "created": articles."{self.article_id}".created,
            "updated": articles."{self.article_id}".updated,
            "column": articles."{self.article_id}".column.title,
            "column_url": articles."{self.article_id}".column.url,
            "column_intro": articles."{self.article_id}".column.intro
        }}"""
        result = jmespath.search(expression, data)
        return result

    def _parse_status_json_data(self, data: Dict) -> Dict:
        expression = f"""{{
                title: status.{self.status_id}.title,
                
                }}"""
        result = jmespath.search(expression, data)
        return result

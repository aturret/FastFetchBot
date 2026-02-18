import json
import re
import traceback
from typing import Dict, Optional, Any
from urllib.parse import urlparse

import httpx
import jmespath
from bs4 import BeautifulSoup
from lxml import etree, html

from fastfetchbot_shared.utils.parse import (
    get_html_text_length,
    format_telegram_short_text,
    unix_timestamp_to_utc,
    wrap_text_into_html,
)
from fastfetchbot_shared.utils.network import get_selector, get_redirect_url, get_response_json, get_random_user_agent, \
    get_content_async, get_response
from fastfetchbot_shared.models.metadata_item import MetadataItem, MediaFile, MessageType
from src.config import JINJA2_ENV, FXZHIHU_HOST
from .config import (
    SHORT_LIMIT,
    ZHIHU_COLUMNS_API_HOST,
    ZHIHU_API_HOST,
    ZHIHU_HOST,
    ALL_METHODS,
    ZHIHU_COOKIES,
    ZHIHU_API_ANSWER_PARAMS
)
from fastfetchbot_shared.utils.logger import logger

environment = JINJA2_ENV
short_text_template = environment.get_template("zhihu_short_text.jinja2")
content_template = environment.get_template("zhihu_content.jinja2")
zhihu_client = httpx.AsyncClient()


def _parse_answer_api_json_data(data: Dict) -> Dict:
    expression = f"""{{
            question_id: question.id,
            title: question.title,
            question_detail: question.detail,
            answer_count: question.answer_count,
            follower_count: question.follower_count,
            question_created: question.created,
            question_updated: question.updated_time,
            author: author.name,
            author_url_token: author.url_token,
            content: content,
            created: created_time
            updated: updated_time,
            comment_count: comment_count,
            voteup_count: voteup_count,
            ip_info: ipInfo
        }}"""
    result = jmespath.search(expression, data)
    return result


def _fix_json_quotes(raw_str):
    """
        通用修复函数：
        1. 修复物理换行
        2. 修复 key: value 结构中 value 内部未正确转义的引号
        3. 修复特殊的 href="null" 等非法结构
        """

    raw_str = raw_str.replace('\n', '\\n').replace('\r', '\\r')
    raw_str = re.sub(r'href="([^\\].*?)"', r'href=\\"\1\\"', raw_str)

    target_keys = ['content','detail']

    for key in target_keys:
        pattern = r'("' + key + r'":\s*")(.*?)("(?=,"[a-z_]+":))'

        def replace_inner_quotes(match):
            prefix = match.group(1)
            body = match.group(2)
            suffix = match.group(3)

            fixed_body = body.replace('\\"', '"').replace('\\&quot;', '').replace('"', '\\"')

            return prefix + fixed_body + suffix

        raw_str = re.sub(pattern, replace_inner_quotes, raw_str, flags=re.DOTALL)

    return raw_str


class Zhihu(MetadataItem):
    def __init__(self, url: str, data: Optional[Any] = None, **kwargs):
        # metadata fields
        self.url: url = url
        self.title: str = ""
        self.author: str = ""
        self.author_url: str = ""
        self.text: str = ""
        self.content: str = ""
        self.media_files: list[MediaFile] = []
        self.category = "zhihu"
        self.message_type: MessageType = MessageType.SHORT
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
        self.upvote: int = 0
        self.retweeted: bool = False
        # reqeust fields
        self.httpx_client = zhihu_client
        self.headers = {"User-Agent": get_random_user_agent(),
                        "Accept": "*/*",
                        "Referer": self.url,
                        "Connection": "keep-alive",
                        }
        if kwargs.get("cookie"):
            self.headers["Cookie"] = kwargs.get("cookie")
        if ZHIHU_COOKIES:
            self.headers["Cookie"] = ZHIHU_COOKIES
        self.method = kwargs.get("method", "fxzhihu")
        self.urlparser = urlparse(self.url)
        self.api_url = ""
        self.status_id = ""
        self.answer_id = ""
        self.question_id = ""
        # other hard-coded fields
        self.zhihu_type_translate = {
            "article": "专栏文章",
            "answer": "回答",
            "status": "想法",
        }

    async def get_item(self) -> dict:
        await self.get_zhihu()
        return self.to_dict()

    async def get_zhihu(self) -> None:
        """
        Main function.
        Get the zhihu item and return the metadata dict.
        :return: Dict
        """
        await self._get_zhihu_item()

    async def _get_zhihu_item(self) -> None:
        """
        Get zhihu item via the corresponding method according to the zhihu type.
        """
        await self._check_zhihu_type()
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
                await self._get_request_url()
                await function_dict[self.zhihu_type]()
                if self.title != "":
                    break
            except Exception as e:
                traceback.print_exc()
                if method == ALL_METHODS[-1]:
                    print("all methods failed")
                    raise e
                else:
                    print(
                        f"zhihu {self.zhihu_type} {self.method} failed, try the next method"
                    )
                continue
        self._zhihu_short_text_process()
        self._zhihu_content_process()
        self.message_type = (
            MessageType.LONG
            if get_html_text_length(self.text) > SHORT_LIMIT
            else MessageType.SHORT
        )

    async def _check_zhihu_type(self) -> None:
        """
        Check the zhihu type of the url. The zhihu type can be one of the following:
        - answer (example: https://www.zhihu.com/question/19998424/answer/603067076)
        - article (example: https://zhuanlan.zhihu.com/p/35142635)
        - status (example: https://www.zhihu.com/pin/1667965059081945088)
        """
        host = self.urlparser.netloc
        path = self.urlparser.path
        logger.debug(
            f"""
        host: {host}
        path: {path}
        """
        )
        if host.startswith("zhuanlan."):
            self.zhihu_type = "article"
            self.article_id = self.urlparser.path.split("/")[-1]
        elif path.startswith("/answer/") or (path.startswith("/question/") and path.find("/answer/") != -1):
            self.zhihu_type = "answer"
            self.answer_id = self.urlparser.path.split("/")[-1]
            if path.find("/question/") != -1:
                self.question_id = self.urlparser.path.split("/")[-3]
            # self.method = "json"
        elif path.startswith("/pin/"):
            self.zhihu_type = "status"
            self.status_id = self.urlparser.path.split("/")[-1]
            # self.method = "api"
        else:
            self.zhihu_type = "unknown"
        self.url = f"https://{host}{path}"

    async def _get_request_url(self) -> None:
        host = self.urlparser.netloc
        path = self.urlparser.path
        request_url_path = path
        if self.method == "fxzhihu":
            self.headers["Content-Type"] = "text/html"
            if self.zhihu_type == "answer":
                if self.question_id:
                    self.request_url = (
                            "https://" + FXZHIHU_HOST + '/question/' + self.question_id + '/answer/' + self.answer_id
                    )
                    return
                self.request_url = (
                        "https://" + FXZHIHU_HOST + '/answer/' + self.answer_id
                )
                return
            elif self.zhihu_type == "article":
                self.request_url = (
                        "https://" + FXZHIHU_HOST + '/p/' + self.article_id
                )
                return
            elif self.zhihu_type == "status":
                self.request_url = (
                        "https://" + FXZHIHU_HOST + '/pin/' + self.status_id
                )
                return
        if self.zhihu_type == "answer":
            if self.method == "api":
                self.request_url = (
                        ZHIHU_API_HOST
                        + "/answers/"
                        + self.answer_id
                        + "?"
                        + ZHIHU_API_ANSWER_PARAMS
                )
                return
            else:
                if path.find("question") != -1:
                    self.question_id = self.urlparser.path.split("/")[-3]
                else:
                    await self._get_question_id()
                request_url_path = "/aria/question/" + self.question_id + "/answer/" + self.answer_id
        elif self.zhihu_type == "article":
            if self.method == "api":
                self.request_url = (
                        ZHIHU_COLUMNS_API_HOST
                        + "/articles/"
                        + self.article_id
                        + "?"
                        + ZHIHU_API_ANSWER_PARAMS
                )
                return
                # TODO: There are two api url to get a single article. The first one may fail in the future.
                # Therefore, I remain the second one.
                # self.request_url = (
                #    ZHIHU_COLUMNS_API_HOST_V2 + self.article_id + "?" + ZHIHU_API_ANSWER_PARAMS)
        elif self.zhihu_type == "status":
            if self.method == "api":
                self.request_url = (
                        "https://www.zhihu.com/api/v4/pins/"
                        + self.urlparser.path.split("/")[-1]
                )
                return
        self.request_url = f"https://{host}{request_url_path}"

    async def _get_zhihu_answer(self) -> None:
        """
        parse the zhihu answer page and get the metadata.
        support methods: html, json. Recommend: json
        """
        if self.method in ["api", "json", "fxzhihu"]:
            answer_data = {}
            if self.method == "api":
                try:
                    json_data = await get_response_json(self.request_url, headers=self.headers,
                                                        client=self.httpx_client)
                    logger.debug(f"json data: {json_data}")
                    answer_data = _parse_answer_api_json_data(json_data)
                    logger.debug(f"answer data: {answer_data}")
                except Exception as e:
                    raise Exception("Cannot get the answer by API")
            elif self.method == "fxzhihu":
                try:
                    resp = await get_response(url=self.request_url, headers=self.headers, client=self.httpx_client)
                    json_data = json.loads(_fix_json_quotes(resp.text))
                    logger.debug(f"json data: {json_data}")
                    answer_data = _parse_answer_api_json_data(json_data)
                    logger.debug(f"answer data: {answer_data}")
                except Exception as e:
                    raise Exception("Cannot get the answer by fxzhihu, error: " + str(e))
            elif self.method == "json":
                try:
                    selector = await get_selector(self.request_url, headers=self.headers)
                    json_data = selector.xpath('string(//script[@id="js-initialData"])')
                    json_data = json.loads(json_data)
                    json_data = json_data["initialState"]["entities"]
                    answer_data = self._parse_answer_json_data(json_data)
                except Exception as e:
                    raise Exception("Cannot get the selector")
            if answer_data == {}:
                raise Exception("Cannot get the answer")
            self._resolve_answer_json_data(answer_data)
        else:
            try:
                selector = await get_selector(self.request_url, headers=self.headers)
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
            except Exception as e:
                raise Exception("Cannot get the answer")
        if (
                self.title == ""
        ):  # TODO: this is not a good way to check if the scraping is successful. To be improved.
            raise Exception("Cannot get the answer")

    async def _get_zhihu_status(self):
        """
        parse the zhihu status page and get the metadata.
        support methods: api, html
        """
        if self.method in ["api", "fxzhihu"]:
            json_data = await get_response_json(self.request_url, headers=self.headers, client=self.httpx_client)
            data = self._resolve_status_api_data(json_data)  # TODO: separate the function to resolve the api data
            self.author = data["author"]
            self.author_url = data["author_url"]
            self.title = data["author"] + "的想法"
            self.raw_content = json_data["content_html"]
            self.media_files.extend(data["media_files"])
            self.date = unix_timestamp_to_utc(data["created"])
            self.updated = unix_timestamp_to_utc(data["updated"])
            self.upvote = data["like_count"]
            if data["origin_pin_id"]:
                self.retweeted = True
                self.origin_pin_url = ZHIHU_HOST + "/pin/" + data["origin_pin_id"]
                self.origin_pin_author = data["origin_pin_data"]["author"]
                self.origin_pin_author_url = data["origin_pin_data"]["author_url"]
                self.origin_pin_raw_content = data["origin_pin_data"]["raw_content"]
                self.origin_pin_date = unix_timestamp_to_utc(data["origin_pin_data"]["created"])
                self.origin_pin_updated = unix_timestamp_to_utc(data["origin_pin_data"]["updated"])
                self.origin_pin_upvote = data["origin_pin_data"]["like_count"]
                self.origin_pin_comment_count = data["origin_pin_data"]["comment_count"]
                self.media_files.extend(data["origin_pin_data"]["media_files"])
        else:
            try:
                selector = await get_selector(self.request_url, headers=self.headers)
            except:
                raise Exception("zhihu request failed")
            if self.method == "json":
                def _process_picture(pictures, content_attr):
                    if not hasattr(self, content_attr):
                        setattr(self, content_attr, "")
                    for pic in pictures:
                        if pic["type"] == "image":
                            if pic["isGif"]:
                                media_type = "gif"
                                setattr(
                                    self,
                                    content_attr,
                                    getattr(self, content_attr)
                                    + f'<br><video controls="controls" src="{pic["originalUrl"]}"><br>',
                                )
                            else:
                                media_type = "image"
                                setattr(
                                    self,
                                    content_attr,
                                    getattr(self, content_attr)
                                    + f'<br><img src="{pic["originalUrl"]}"><br>',
                                )
                        elif pic["type"] == "video":
                            media_type = "video"
                            setattr(
                                self,
                                content_attr,
                                getattr(self, content_attr)
                                + f'<br><video controls="controls" src="{pic["originalUrl"]}"><br>',
                            )
                        media_item = MediaFile.from_dict(
                            {
                                "media_type": media_type,
                                "url": pic["originalUrl"],
                                "caption": "",
                            }
                        )
                        self.media_files.append(media_item)

                json_data = selector.xpath('string(//script[@id="js-initialData"])')
                json_data = json.loads(json_data)["initialState"]["entities"]
                status_data = self._parse_status_json_data(json_data)
                if status_data["origin_pin_url"] is not None:
                    self.retweeted = True
                    self.origin_pin_url = status_data["origin_pin_url"]
                    self.origin_pin_author = status_data["origin_pin_author"]
                    self.origin_pin_author_url = (
                            ZHIHU_HOST
                            + "/people/"
                            + status_data["origin_pin_author_url_token"]
                    )
                    self.origin_pin_raw_content = status_data["origin_pin_content"]
                    self.origin_pin_date = unix_timestamp_to_utc(
                        status_data["origin_pin_created"]
                    )
                    self.origin_pin_updated = unix_timestamp_to_utc(
                        status_data["origin_pin_updated"]
                    )
                    self.origin_pin_upvote = status_data["origin_pin_like_count"]
                    self.origin_pin_comment_count = status_data[
                        "origin_pin_comment_count"
                    ]
                    _process_picture(
                        status_data["origin_pin_pictures"], "origin_pin_pic_content"
                    )
                self.title = status_data["author"] + "的想法"
                self.author = status_data["author"]
                self.author_url = (
                        ZHIHU_HOST + "/people/" + status_data["author_url_token"]
                )
                self.raw_content = status_data["content"]
                self.date = unix_timestamp_to_utc(status_data["created"])
                self.updated = unix_timestamp_to_utc(status_data["updated"])
                self.upvote = status_data["like_count"]
                self.comment_count = status_data["comment_count"]
                _process_picture(status_data["pictures"], "pic_content")
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
                ):  # check if the status is a retweet
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
                    ):  # if the retweet content including pictures
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
                self.author = selector.xpath(
                    'string(//div[@class="AuthorInfo"]//meta[@itemprop="name"]/@content)'
                )
                self.author_url = selector.xpath(
                    'string(//div[@class="AuthorInfo"]//meta[@itemprop="url"]/@content)'
                )
                self.title = self.author + "的想法"

    async def _get_zhihu_article(self):
        self.zhihu_type = "article"
        if self.method in ["api", "fxzhihu"]:
            try:
                json_data = await get_response_json(self.request_url, headers=self.headers, client=self.httpx_client)
                self.title = json_data["title"]
                self.raw_content = json_data["content"]
                self.author = json_data["author"]["name"]
                self.author_url = json_data["author"]["url"]
                self.upvote = json_data["voteup_count"]
            except Exception as e:
                raise Exception("zhihu request failed")
        else:
            try:
                selector = await get_selector(self.request_url, headers=self.headers)
            except Exception as e:
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
        def _html_process(raw_html: str) -> str:
            soup = BeautifulSoup(raw_html, "html.parser")
            for img_tag in soup.find_all("img"):
                if img_tag["src"].find("data:image") != -1:
                    continue
                if self.zhihu_type != "status":
                    media_item = MediaFile.from_dict(
                        {"media_type": "image", "url": img_tag["src"], "caption": ""}
                    )
                    self.media_files.append(media_item)
                src_value = img_tag["src"]
                img_tag.attrs.clear()
                img_tag["src"] = src_value
            for figure in soup.find_all("figure"):
                figure.append(BeautifulSoup("<br>", "html.parser"))
                figure.decompose()
            for a_tag in soup.find_all("a"):
                if not a_tag.has_attr("href"):
                    a_tag.unwrap()
                    continue
                href_value = a_tag["href"]
                a_tag.attrs.clear()
                a_tag["href"] = href_value
            for br_tag in soup.find_all("br"):
                br_tag.replace_with("\n")
            return str(soup)

        data = self.__dict__
        data["translated_zhihu_type"] = self.zhihu_type_translate[self.zhihu_type]
        raw_content = self.raw_content.replace("</br></br>", "\n")
        raw_content = _html_process(raw_content)
        data["content"] = raw_content
        if self.zhihu_type == "status" and self.retweeted:
            origin_pin_content = self.origin_pin_raw_content.replace("</br></br>", "\n")
            origin_pin_content = _html_process(origin_pin_content)
            data["origin_pin_content"] = origin_pin_content
        self.text = short_text_template.render(data=data)
        soup = BeautifulSoup(self.text, "html.parser")
        soup = format_telegram_short_text(soup)
        for h_tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            if h_tag.text != "":
                h_tag.append(BeautifulSoup("<br>", "html.parser"))
            h_tag.unwrap()
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
        if self.text.endswith("\n"):
            self.text = self.text[:-1]

    def _zhihu_content_process(self):
        data = self.__dict__
        data["raw_content"] = wrap_text_into_html(
            data["raw_content"].replace("\n", "<br>"), True
        )
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
        self.question_id = result["question_id"]
        expression = f"""{{
                        "title": questions."{self.question_id}".title,
                        "question_detail": questions."{self.question_id}".detail,
                        "answer_count": questions."{self.question_id}".answerCount,
                        "follower_count": questions."{self.question_id}".followerCount,
                        "question_created": questions."{self.question_id}".created,
                        "question_updated": questions."{self.question_id}".updatedTime
                    }}"""
        result.update(jmespath.search(expression, data))
        return result

    def _resolve_answer_json_data(self, answer_data: Dict) -> None:
        self.question = answer_data["question_detail"] or ""
        self.question_date = unix_timestamp_to_utc(
            answer_data["question_created"] or ""
        ) or ""
        self.question_updated = unix_timestamp_to_utc(
            answer_data["question_updated"] or ""
        ) or ""
        self.question_follower_count = answer_data["follower_count"] or 0
        self.question_answer_count = answer_data["answer_count"] or 0
        self.title = answer_data["title"] or ""
        self.author = answer_data["author"] or ""
        self.author_url = (
                                  ZHIHU_HOST + "/people/" + answer_data["author_url_token"] or ""
                          ) or ""
        self.raw_content = answer_data["content"] or ""
        self.date = unix_timestamp_to_utc(answer_data["created"] or "") or ""
        self.updated = unix_timestamp_to_utc(answer_data["updated"] or "") or ""
        self.comment_count = answer_data["comment_count"] or 0
        self.upvote = answer_data["voteup_count"] or 0
        self.ip_info = answer_data["ip_info"] or ""

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

    @staticmethod
    def _resolve_status_api_data(data: Dict) -> Dict:
        result = {
            "author": data["author"]["name"],
            "author_url": ZHIHU_HOST + "/people/" + data["author"]["url_token"],
            "created": data["created"],
            "updated": data["updated"],
            "text": None,
            "raw_content": data["content_html"],
            "like_count": data["like_count"],
            "comment_count": data["comment_count"],
            "media_files": [],
            "origin_pin_id": None,
        }
        for content in data["content"]:
            if content["type"] == "text":
                result["text"] = content["content"]
            elif content["type"] == "image":
                media_item = MediaFile.from_dict(
                    {
                        "media_type": "image",
                        "url": content["original_url"],
                        "caption": "",
                    }
                )
                result["media_files"].append(media_item)
            elif content["type"] == "video":
                media_item = MediaFile.from_dict(
                    {
                        "media_type": "video",
                        "url": content["video_info"]["playlist"]["hd"]["play_url"],
                        "caption": "",
                    }
                )
                result["media_files"].append(media_item)
        if "origin_pin" in data:
            result["origin_pin_id"] = data["origin_pin"]["id"]
            result["origin_pin_data"] = Zhihu._resolve_status_api_data(data["origin_pin"])
        return result

    def _parse_status_json_data(self, data: Dict) -> Dict:
        expression = f"""{{
                "author_url_token": pins."{self.status_id}".author,
                "created": pins."{self.status_id}".created,
                "updated": pins."{self.status_id}".updated,
                "content": pins."{self.status_id}".content[0].content,
                "pictures": pins."{self.status_id}".content[1:],
                "like_count": pins."{self.status_id}".likeCount,
                "comment_count": pins."{self.status_id}".commentCount,
                "origin_pin_url": pins."{self.status_id}".originPin.url,
                "origin_pin_author": pins."{self.status_id}".originPin.author.name,
                "origin_pin_author_url_token": pins."{self.status_id}".originPin.author.urlToken,
                "origin_pin_created": pins."{self.status_id}".originPin.created,
                "origin_pin_updated": pins."{self.status_id}".originPin.updated,
                "origin_pin_content": pins."{self.status_id}".originPin.content[0].content,
                "origin_pin_pictures": pins."{self.status_id}".originPin.content[1:],
                "origin_pin_like_count": pins."{self.status_id}".originPin.likeCount,
                "origin_pin_comment_count": pins."{self.status_id}".originPin.commentCount
                }}"""
        result = jmespath.search(expression, data)
        print(result)
        author_url_token = result["author_url_token"]
        expression = f"""{{
                        "author": users."{author_url_token}".name
                        }}"""
        result.update(jmespath.search(expression, data))
        return result

    async def _get_question_id(self):
        redirected_url = await get_redirect_url(self.url)
        self.question_id = urlparse(redirected_url).path.split("/")[2]

    def _generate_zhihu_cookie(self):
        # TODO: a more elegant way to generate the zhihu cookie
        pass

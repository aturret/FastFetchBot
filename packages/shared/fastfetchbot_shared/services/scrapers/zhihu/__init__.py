import json
import re
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
from fastfetchbot_shared.utils.network import get_selector, get_redirect_url, get_random_user_agent, \
    get_content_async, get_response
from fastfetchbot_shared.models.metadata_item import MetadataItem, MediaFile, MessageType
from fastfetchbot_shared.exceptions import ScraperError, ScraperParseError
from fastfetchbot_shared.services.scrapers.config import settings, JINJA2_ENV
from .config import (
    SHORT_LIMIT,
    ZHIHU_COLUMNS_API_HOST,
    ZHIHU_API_HOST,
    ZHIHU_HOST,
    ALL_METHODS,
    ZHIHU_COOKIES,
    ZHIHU_API_COOKIE,
    ZHIHU_API_ANSWER_PARAMS,
    ZHIHU_DAILY_API,
)
from .content_processing import fix_images_and_links, extract_references, unmask_zhihu_links
from .signature import ZSE93, get_x_zse_96
from fastfetchbot_shared.utils.logger import logger

environment = JINJA2_ENV
short_text_template = environment.get_template("zhihu_short_text.jinja2")
content_template = environment.get_template("zhihu_content.jinja2")
zhihu_client = httpx.AsyncClient()

# Methods that call Zhihu's API v4 directly and share its JSON parsing.
API_METHODS = ("api", "signed_api")
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)
# Video playlist qualities, best first.
VIDEO_QUALITIES = ("fhd", "hd", "sd", "ld")


async def _zhihu_api_get_json(url: str, headers: dict = None, client: httpx.AsyncClient = None) -> dict:
    """GET a Zhihu JSON endpoint, raising ScraperError with Zhihu's own reason on failure."""
    try:
        resp = await get_response(url, headers=headers, client=client)
    except httpx.HTTPError as e:
        raise ScraperError(f"知乎请求失败：{type(e).__name__}") from e
    try:
        data = resp.json()
    except ValueError as e:
        raise ScraperError(f"知乎接口返回的不是 JSON（HTTP {resp.status_code}）") from e
    if not isinstance(data, dict):
        raise ScraperError(f"知乎接口返回的不是 JSON 对象（HTTP {resp.status_code}）")
    error = data.get("error")
    if error:
        code, message = (error.get("code"), error.get("message")) if isinstance(error, dict) else (None, error)
        raise ScraperError(f"知乎接口错误 {code}：{message}")
    if not 200 <= resp.status_code < 300:
        raise ScraperError(f"知乎接口返回 HTTP {resp.status_code}")
    return data


def _cookie_value(cookie: str | None, name: str) -> str | None:
    for part in (cookie or "").split(";"):
        key, _, value = part.strip().partition("=")
        if key == name and value:
            return value
    return None


def _first_answer_id(data: dict) -> str | None:
    """First answer ID from a question's answers API response; None if there are no answers.

    Raises ScraperParseError when the response does not have the expected shape.
    """
    answers = data.get("data")
    if not isinstance(answers, list):
        raise ScraperParseError("知乎问题的回答列表数据结构异常")
    if not answers:
        return None
    first = answers[0]
    if not isinstance(first, dict) or not first.get("id"):
        raise ScraperParseError("知乎问题的回答数据结构异常")
    return str(first["id"])


def _is_formula_or_placeholder(src: str) -> bool:
    return src.startswith("data:image") or "/equation" in src


def _positive_int(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _select_video(content: dict) -> dict | None:
    """Pick the best playable stream of a pin video: fhd > hd > sd > ld > first.

    Supports `video_info.playlist` as a {quality: stream} dict and `playlist` as a
    list of streams with a `quality` key. A stream's address is `play_url` or `url`.
    """
    video_info = content.get("video_info") or {}
    playlist = video_info.get("playlist") if "video_info" in content else content.get("playlist")
    if isinstance(playlist, dict):
        streams = [dict(stream, quality=quality) for quality, stream in playlist.items() if isinstance(stream, dict)]
    elif isinstance(playlist, list):
        streams = [stream for stream in playlist if isinstance(stream, dict)]
    else:
        streams = []
    streams = [s for s in streams if s.get("play_url") or s.get("url")]
    if not streams:
        return None
    rank = {quality: i for i, quality in enumerate(VIDEO_QUALITIES)}
    best = min(streams, key=lambda s: rank.get(s.get("quality"), len(rank)))
    return {
        "url": best.get("play_url") or best.get("url"),
        "width": _positive_int(best.get("width")),
        "height": _positive_int(best.get("height")),
        "duration": _positive_int(video_info.get("duration") or content.get("duration")),
    }


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


def _parse_zhihu_timestamp(timestamp: Any) -> int | None:
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp <= 0:
        return None
    return timestamp


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
        self.timestamp = None
        self.retweet_html = ""
        self.upvote: int = 0
        self.retweeted: bool = False
        # reqeust fields
        self.httpx_client = zhihu_client
        self.headers = {
            "User-Agent": "node",
            "Accept": "*/*",
            "Referer": self.url,
            "Connection": "keep-alive",
        }
        cookie = kwargs.get("cookie") or ZHIHU_COOKIES or ZHIHU_API_COOKIE
        if cookie:
            self.headers["Cookie"] = cookie
        self.method = kwargs.get("method", "api")
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

    def _request_headers(self, url: str) -> dict:
        """Headers for the current method; `signed_api` adds the x-zse-96 signature."""
        if self.method != "signed_api":
            return self.headers
        cookie = self.headers.get("Cookie")
        d_c0 = _cookie_value(cookie, "d_c0")
        if not d_c0:
            raise ScraperError("签名请求需要 Cookie 里的 d_c0")
        # Sign exactly what goes on the wire.
        sent_url = str(httpx.URL(url))
        return {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "*/*",
            "Referer": "https://www.zhihu.com/",
            "Cookie": cookie,
            "x-requested-with": "fetch",
            "x-zse-93": ZSE93,
            "x-zse-96": get_x_zse_96(sent_url, d_c0),
        }

    def _method_order(self, methods) -> list[str]:
        """Try `signed_api` first when d_c0 is available.

        Live checks showed unsigned API calls failing on answers and articles
        (10003 / 40362 risk control) while signed ones succeed, so an unsigned
        attempt first only wastes a request and may draw more risk control.
        """
        methods = list(methods)
        if "signed_api" in methods and _cookie_value(self.headers.get("Cookie"), "d_c0"):
            methods.remove("signed_api")
            methods.insert(0, "signed_api")
        return methods

    async def _api_get_json(self, url: str) -> dict:
        return await _zhihu_api_get_json(url, headers=self._request_headers(url), client=self.httpx_client)

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
        await self._resolve_daily_url()
        await self._check_zhihu_type()
        if self.zhihu_type == "question":
            await self._resolve_question_answer()
        function_dict = {
            "answer": self._get_zhihu_answer,
            "article": self._get_zhihu_article,
            "status": self._get_zhihu_status,
        }
        if self.zhihu_type not in function_dict:
            raise ScraperError(f"不支持的知乎链接：{self.url}")
        errors: list[str] = []
        methods = self._method_order(ALL_METHODS)
        for method in methods:
            try:
                if self.method not in methods:
                    self.method = "api"
                else:
                    self.method = method
                await self._get_request_url()
                await function_dict[self.zhihu_type]()
                if self.title != "":
                    break
            except Exception as e:
                logger.exception(f"Zhihu scraper method {method} failed")
                errors.append(f"{method}: {str(e) or type(e).__name__}"[:300])
                if method == methods[-1]:
                    logger.error("All Zhihu scraper methods failed")
                    raise ScraperError("知乎内容获取失败：" + "；".join(errors)) from e
                else:
                    logger.warning(
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
        - question without an answer (example: https://www.zhihu.com/question/19998424),
          resolved to its first answer by _resolve_question_answer
        """
        host = self.urlparser.netloc
        path = self.urlparser.path
        logger.debug(
            f"""
        host: {host}
        path: {path}
        """
        )
        appview = re.search(r"/appview/p/(\d+)", path)
        question_only = re.fullmatch(r"/question/(\d+)/?", path)
        if appview:
            self.zhihu_type = "article"
            self.article_id = appview.group(1)
            self._set_url(f"https://zhuanlan.zhihu.com/p/{self.article_id}")
            return
        if question_only:
            self.zhihu_type = "question"
            self.question_id = question_only.group(1)
            self.url = f"https://{host}{path}"
            return
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

    def _set_url(self, url: str) -> None:
        self.url = url
        self.urlparser = urlparse(url)
        self.headers["Referer"] = url

    async def _resolve_daily_url(self) -> None:
        """Zhihu Daily stories link to an original Zhihu post; scrape that instead."""
        if not self.urlparser.netloc.startswith("daily."):
            return
        match = re.search(r"/story/(\d+)", self.urlparser.path)
        if not match:
            raise ScraperError(f"无法识别知乎日报链接：{self.url}")
        story = await _zhihu_api_get_json(
            f"{ZHIHU_DAILY_API}/{match.group(1)}",
            headers={"User-Agent": BROWSER_USER_AGENT},
            client=self.httpx_client,
        )
        soup = BeautifulSoup(story.get("body") or "", "html.parser")
        origin = next(
            (a.get("href") for a in soup.find_all("a") if "查看知乎原文" in a.get_text() and a.get("href")),
            None,
        )
        if not origin:
            raise ScraperError("这篇知乎日报没有对应的知乎原文")
        logger.info(f"Zhihu daily story resolved to {origin}")
        self._set_url(origin)

    async def _resolve_question_answer(self) -> None:
        """Turn a question-only link into its first answer (default ranking)."""
        url = (
            f"{ZHIHU_API_HOST}/questions/{self.question_id}/answers"
            "?limit=1&offset=0&sort_by=default"
        )
        errors: list[str] = []
        original_method = self.method
        for method in self._method_order(API_METHODS):
            self.method = method
            try:
                answer_id = _first_answer_id(await self._api_get_json(url))
                break
            except ScraperError as e:  # includes ScraperParseError: try the next method
                errors.append(f"{method}: {e}")
        else:
            self.method = original_method
            raise ScraperError("知乎问题的回答获取失败：" + "；".join(errors))
        self.method = original_method
        if answer_id is None:
            raise ScraperError("该知乎问题还没有回答")
        self.answer_id = answer_id
        self.zhihu_type = "answer"
        self._set_url(f"https://www.zhihu.com/question/{self.question_id}/answer/{self.answer_id}")

    async def _get_request_url(self) -> None:
        host = self.urlparser.netloc
        path = self.urlparser.path
        request_url_path = path
        if self.method == "fxzhihu":
            self.headers["Content-Type"] = "text/html"
            if self.zhihu_type == "answer":
                if self.question_id:
                    self.request_url = (
                            "https://" + settings.FXZHIHU_HOST + '/question/' + self.question_id + '/answer/' + self.answer_id
                    )
                    return
                self.request_url = (
                        "https://" + settings.FXZHIHU_HOST + '/answer/' + self.answer_id
                )
                return
            elif self.zhihu_type == "article":
                self.request_url = (
                        "https://" + settings.FXZHIHU_HOST + '/p/' + self.article_id
                )
                return
            elif self.zhihu_type == "status":
                self.request_url = (
                        "https://" + settings.FXZHIHU_HOST + '/pin/' + self.status_id
                )
                return
        if self.zhihu_type == "answer":
            if self.method in API_METHODS:
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
            if self.method in API_METHODS:
                self.request_url = (
                        ZHIHU_API_HOST
                        + "/articles/"
                        + self.article_id
                )
                return
        elif self.zhihu_type == "status":
            if self.method in API_METHODS:
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
        if self.method in [*API_METHODS, "json", "fxzhihu"]:
            answer_data = {}
            if self.method in API_METHODS:
                json_data = await self._api_get_json(self.request_url)
                logger.debug(f"json data: {json_data}")
                try:
                    answer_data = _parse_answer_api_json_data(json_data)
                    logger.debug(f"answer data: {answer_data}")
                except Exception as e:
                    raise ScraperParseError("Cannot parse the answer from API data") from e
            elif self.method == "fxzhihu":
                try:
                    resp = await get_response(url=self.request_url, headers=self.headers, client=self.httpx_client)
                    json_data = json.loads(_fix_json_quotes(resp.text))
                    logger.debug(f"json data: {json_data}")
                    answer_data = _parse_answer_api_json_data(json_data)
                    logger.debug(f"answer data: {answer_data}")
                except Exception as e:
                    raise ScraperError("Cannot get the answer by fxzhihu, error: " + str(e)) from e
            elif self.method == "json":
                try:
                    selector = await get_selector(self.request_url, headers=self.headers)
                    json_data = selector.xpath('string(//script[@id="js-initialData"])')
                    json_data = json.loads(json_data)
                    json_data = json_data["initialState"]["entities"]
                    answer_data = self._parse_answer_json_data(json_data)
                except Exception as e:
                    raise ScraperParseError("Cannot get the selector") from e
            if answer_data == {}:
                raise ScraperError("Cannot get the answer")
            self._resolve_answer_json_data(answer_data)
            # Apply FxZhihu-style content processing for api method
            if self.method in API_METHODS:
                self.raw_content = fix_images_and_links(self.raw_content)
                self.raw_content = unmask_zhihu_links(self.raw_content)
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
                raise ScraperError("Cannot get the answer") from e
        if (
                self.title == ""
        ):  # TODO: this is not a good way to check if the scraping is successful. To be improved.
            raise ScraperError("Cannot get the answer")

    async def _get_zhihu_status(self):
        """
        parse the zhihu status page and get the metadata.
        support methods: api, html
        """
        if self.method in [*API_METHODS, "fxzhihu"]:
            json_data = await self._api_get_json(self.request_url)
            data = self._resolve_status_api_data(json_data)
            self.author = data["author"]
            self.author_url = data["author_url"]
            self.title = data["author"] + "的想法"
            self.raw_content = json_data.get("content_html", "")
            # Apply FxZhihu-style content processing for api method
            if self.method in API_METHODS:
                self.raw_content = fix_images_and_links(self.raw_content)
                self.raw_content = unmask_zhihu_links(self.raw_content)
            self.media_files.extend(data["media_files"])
            self.date = unix_timestamp_to_utc(data["created"])
            self.timestamp = _parse_zhihu_timestamp(data["created"])
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
            except Exception as e:
                raise ScraperError("zhihu request failed") from e
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
                self.timestamp = _parse_zhihu_timestamp(status_data["created"])
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
                        logger.debug(f"retweet_html type: {type(self.retweet_html)}")
                        logger.debug(self.retweet_html)
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
                        logger.debug(self.retweet_html)
                self.author = selector.xpath(
                    'string(//div[@class="AuthorInfo"]//meta[@itemprop="name"]/@content)'
                )
                self.author_url = selector.xpath(
                    'string(//div[@class="AuthorInfo"]//meta[@itemprop="url"]/@content)'
                )
                self.title = self.author + "的想法"

    async def _get_zhihu_article(self):
        self.zhihu_type = "article"
        if self.method in [*API_METHODS, "fxzhihu"]:
            json_data = await self._api_get_json(self.request_url)
            try:
                self.title = json_data["title"]
                self.raw_content = json_data["content"]
                self.author = json_data["author"]["name"]
                self.author_url = json_data["author"]["url"]
                self.upvote = json_data["voteup_count"]
                self.comment_count = json_data.get("comment_count", 0)
                self.date = unix_timestamp_to_utc(json_data.get("created", 0))
                self.timestamp = _parse_zhihu_timestamp(json_data.get("created", 0))
                self.updated = unix_timestamp_to_utc(json_data.get("updated", 0))
                if json_data.get("column"):
                    self.column = json_data["column"].get("title", "")
                    self.column_url = json_data["column"].get("url", "")
                    self.column_intro = json_data["column"].get("intro", "")
                # Apply FxZhihu-style content processing for api method
                if self.method in API_METHODS:
                    self.raw_content = fix_images_and_links(self.raw_content)
                    self.raw_content = unmask_zhihu_links(self.raw_content)
            except Exception as e:
                raise ScraperParseError("Cannot parse the article from API data") from e
        else:
            try:
                selector = await get_selector(self.request_url, headers=self.headers)
            except Exception as e:
                raise ScraperError("zhihu request failed") from e
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
                self.timestamp = _parse_zhihu_timestamp(article_data["created"])
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
                if _is_formula_or_placeholder(img_tag["src"]):
                    # Formula (/equation) and placeholder images stay inline only.
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
        self.timestamp = _parse_zhihu_timestamp(answer_data["created"] or "")
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
        # Handle both API response formats (reaction.statistics vs direct fields)
        if "reaction" in data:
            like_count = data["reaction"]["statistics"]["up_vote_count"]
            comment_count = data["reaction"]["statistics"]["comment_count"]
        else:
            like_count = data.get("like_count", 0)
            comment_count = data.get("comment_count", 0)

        result = {
            "author": data["author"]["name"],
            "author_url": ZHIHU_HOST + "/people/" + data["author"].get("url_token", ""),
            "created": data["created"],
            "updated": data["updated"],
            "text": None,
            "raw_content": data.get("content_html", ""),
            "like_count": like_count,
            "comment_count": comment_count,
            "media_files": [],
            "origin_pin_id": None,
        }
        for content in data.get("content", []):
            if content["type"] == "text":
                result["text"] = content.get("content", "")
            elif content["type"] == "image":
                result["media_files"].append(
                    MediaFile(
                        media_type="image",
                        url=content["original_url"],
                        caption="",
                        width=_positive_int(content.get("width")),
                        height=_positive_int(content.get("height")),
                    )
                )
            elif content["type"] == "video":
                video = _select_video(content)
                if video:
                    result["media_files"].append(MediaFile(media_type="video", caption="", **video))
        if "origin_pin" in data and data["origin_pin"]:
            result["origin_pin_id"] = str(data["origin_pin"]["id"])
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
        logger.debug(result)
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

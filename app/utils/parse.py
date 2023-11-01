import datetime
import os
import re
import mimetypes
from typing import Optional
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup

from app.models.url_metadata import UrlMetadata
from app.utils.config import SOCIAL_MEDIA_WEBSITE_PATTERNS, VIDEO_WEBSITE_PATTERNS

mimetypes.init()


def get_html_text_length(html: str) -> int:
    if html is None:
        return 0
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    return len(text)


def format_telegram_short_text(soup: BeautifulSoup) -> BeautifulSoup:
    decompose_list = ["br"]
    unwrap_list = ["span", "div", "blockquote", "h2", "ol", "ul"]
    new_line_list = ["p", "li"]
    for decompose in decompose_list:
        for item in soup.find_all(decompose):
            item.decompose()
    for unwrap in unwrap_list:
        for item in soup.find_all(unwrap):
            item.unwrap()
    for (
        new_line
    ) in (
        new_line_list
    ):  # add a new line after each <p> and <li> tag and then remove the tag(unwrapping)
        for item in soup.find_all(new_line):
            item.append(BeautifulSoup("<br>", "html.parser"))
            item.unwrap()
    return soup


def unix_timestamp_to_utc(timestamp: int) -> str | None:
    if not timestamp:
        return None
    utc_time = datetime.datetime.utcfromtimestamp(timestamp)
    beijing_time = utc_time + datetime.timedelta(hours=8)
    return beijing_time.strftime("%Y-%m-%d %H:%M")


def second_to_time(second: int) -> str:
    m, s = divmod(second, 60)
    h, m = divmod(m, 60)
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)


async def check_url_type(url: str) -> UrlMetadata:
    url_object = urlparse(url)
    url_main = str(url_object.hostname) + str(url_object.path)
    source, content_type = "unknown", "unknown"
    # check if the url is a social media platform website
    for website, patterns in SOCIAL_MEDIA_WEBSITE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_main):
                source = website
                content_type = "social_media"
    # check if the url is a video website
    if source == "unknown":
        for website, patterns in VIDEO_WEBSITE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_main):
                    source = website
                    content_type = "video"
    # clear the url query
    if source not in ["youtube", "wechat"]:
        url = url_object.scheme + "://" + url_object.netloc + url_object.path
    # TODO: check if the url is from Mastodon, according to the request cookie
    return UrlMetadata(url=url, source=source, content_type=content_type)


def get_ext_from_url(url: str) -> str:
    url_object = urlparse(url)
    filename = unquote(url_object.path)
    ext = os.path.splitext(filename)[1]
    # check if ext in mimetypes.types_map
    if ext in mimetypes.types_map:
        return ext
    else:
        return None


def wrap_text_into_html(text: str, is_html: bool = False) -> str:
    if is_html:
        soup = BeautifulSoup(text, "html.parser")
        for item in soup.find_all("br"):
            item.replace_with("\n")
        text = str(soup)
        print(text)
    split_pivot = "\n" if is_html is False else "<br>"
    text_list = text.split(split_pivot)
    text_list = [f"<p>{item}</p>" for item in text_list if item.strip() != ""]
    text = "".join(text_list)
    return text


def get_bool(value: Optional[str], default: bool = True) -> bool:
    true_values = ("True", "true", "1", "yes", "on")
    false_values = ("False", "false", "0", "no", "off")

    if value is None:
        return default
    value = value.lower()

    if value in true_values:
        return True
    elif value in false_values:
        return False
    else:
        return default


def get_env_bool(env, var_name: Optional[str], default: bool = False):
    """Retrieve environment variable as a boolean."""
    value = env.get(var_name, "").lower()
    return get_bool(value, default)

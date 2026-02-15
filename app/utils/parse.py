import datetime
import os
import re
import mimetypes
from typing import Optional
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup

from app.models.url_metadata import UrlMetadata
from app.utils.config import SOCIAL_MEDIA_WEBSITE_PATTERNS, VIDEO_WEBSITE_PATTERNS, BANNED_PATTERNS

TELEGRAM_TEXT_LIMIT = 900

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


def string_to_list(string: str, divider: str = ",") -> list:
    if string is None:
        return []
    return string.split(divider)


async def get_url_metadata(url: str, ban_list: Optional[list] = None) -> UrlMetadata:
    if not ban_list:
        ban_list = []
    url_parser = urlparse(url)
    url_main = str(url_parser.hostname) + str(url_parser.path)
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
    if source not in ["youtube", "bilibili", "wechat"]:
        url = url_parser.scheme + "://" + url_parser.netloc + url_parser.path
    if source in ban_list:
        source = "banned"
        content_type = "banned"
    else:
        for item in BANNED_PATTERNS:
            if re.search(item, url):
                source = "banned"
                content_type = "banned"
                break
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
    text_list = text.split("\n")
    text_list = [f"<p>{item}</p>" for item in text_list if item.strip() != ""]
    text = "".join(text_list)
    return text


def telegram_message_html_trim(html_content: str, trim_length: int = TELEGRAM_TEXT_LIMIT) -> str:
    from bs4 import Doctype

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove DOCTYPE declarations
    for item in soup.contents:
        if isinstance(item, Doctype):
            item.extract()

    # Decompose tags that should be removed entirely (with their content)
    for tag_name in ["img", "script", "style", "head", "meta", "link", "noscript", "iframe", "svg", "form", "input", "button"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Unwrap structural/layout tags — keep their text, discard the wrapper
    for tag_name in ["div", "span", "section", "article", "nav", "header", "footer",
                     "main", "aside", "figure", "figcaption", "html", "body"]:
        for tag in soup.find_all(tag_name):
            tag.unwrap()

    # Convert headings to bold text with line break
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            tag.name = "b"

    # Unwrap <p> tags (keep text content)
    for tag in soup.find_all("p"):
        tag.unwrap()

    html_content = str(soup).strip()

    if len(html_content) <= trim_length:
        return html_content

    # Initial trimming
    trimmed_content = html_content[:trim_length]

    # Find the position of the last complete tag in the trimmed content
    last_complete_pos = trimmed_content.rfind('<')
    if last_complete_pos != -1:
        trimmed_content = trimmed_content[:last_complete_pos]

    # Remove any incomplete tags by ensuring each tag is closed
    cleaned_html = ''
    open_tags = []

    tag_pattern = re.compile(r'<(/?)([a-zA-Z0-9]+)([^>]*)>')
    pos = 0

    while pos < len(trimmed_content):
        match = tag_pattern.search(trimmed_content, pos)
        if not match:
            break

        start, end = match.span()
        cleaned_html += trimmed_content[pos:start]

        closing, tag_name, attributes = match.groups()

        if closing:
            if open_tags and open_tags[-1] == tag_name:
                open_tags.pop()
                cleaned_html += match.group(0)
        else:
            if not attributes.endswith('/'):
                open_tags.append(tag_name)
                cleaned_html += match.group(0)

        pos = end

    cleaned_html += trimmed_content[pos:]

    # Ensure to close all open tags
    for tag in reversed(open_tags):
        cleaned_html += f'</{tag}>'

    return cleaned_html + ' ...'


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

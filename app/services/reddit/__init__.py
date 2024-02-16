import re
from typing import Optional, Any

import asyncpraw
from bs4 import BeautifulSoup

from app.models.metadata_item import MetadataItem, MessageType, MediaFile
from app.config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_PASSWORD,
    REDDIT_USERNAME,
    JINJA2_ENV,
)
from app.utils.parse import unix_timestamp_to_utc, get_html_text_length
from app.utils.network import get_redirect_url

short_text_template = JINJA2_ENV.get_template("reddit_short_text.jinja2")
content_template = JINJA2_ENV.get_template("reddit_content.jinja2")


class Reddit(MetadataItem):
    def __init__(self, url, data: Optional[Any] = None, **kwargs):
        self.url = url
        self.category = "reddit"
        self.media_files = []
        self.message_type = MessageType.LONG

    async def get_item(self) -> dict:
        await self.get_reddit()
        return self.to_dict()

    async def get_reddit(self) -> None:
        self.url = await get_redirect_url(self.url)
        reddit_data = await self._get_reddit_data()
        await self._process_reddit_data(reddit_data)

    async def _get_reddit_data(self) -> dict:
        reddit_user_agent = f"testscript by u/{REDDIT_USERNAME}"
        reddit = asyncpraw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            password=REDDIT_PASSWORD,
            user_agent=reddit_user_agent,
            username=REDDIT_USERNAME,
        )
        submission = await reddit.submission(url=self.url)
        return submission.__dict__

    async def _process_reddit_data(self, reddit_data) -> None:
        self.url = "https://www.reddit.com" + reddit_data["permalink"]
        self.title = reddit_data["title"]
        self.author = reddit_data["author"].name
        self.author_url = f"https://www.reddit.com/user/{self.author}"
        self.raw_content = reddit_data["selftext_html"] or ""
        self.created = unix_timestamp_to_utc(int(reddit_data["created_utc"]))
        self.score = reddit_data["score"]
        self.comments_count = reddit_data["num_comments"]
        self.upvote_ratio = reddit_data["upvote_ratio"]
        self.subreddit = reddit_data["subreddit"].display_name
        self.subreddit_name_prefixed = reddit_data["subreddit_name_prefixed"]
        self.subreddit_url = (
            f"https://www.reddit.com/{reddit_data['subreddit_name_prefixed']}"
        )
        content_html = self.raw_content
        if "media_metadata" in reddit_data:
            for media_item in reddit_data["media_metadata"].values():
                if media_item["e"] == "Image":
                    media_type = "image"
                    media_url = media_item["s"]["u"]
                elif media_item["e"] == "AnimatedImage":
                    media_type = "video"
                    media_url = media_item["s"]["gif"]
                elif media_item["e"] == "Video":
                    media_type = "video"
                    media_url = media_item["s"]["gif"]
                else:
                    continue
                self.media_files.append(
                    MediaFile(
                        media_type=media_type,
                        url=media_url,
                        caption="",
                    )
                )
        if reddit_data.get("post_hint", "") == "image":
            preview_url = reddit_data["preview"]["images"][0]["source"]["url"]
            self.media_files.append(
                MediaFile(
                    media_type="image",
                    url=preview_url,
                    caption="",
                )
            )
            preview_image_html_tag = f"<img src='{preview_url}'>"
            content_html += preview_image_html_tag
        self.raw_content = re.sub(r"<!--.*?-->", "", self.raw_content, flags=re.DOTALL)
        soup = BeautifulSoup(self.raw_content, "html.parser")
        # resolve content
        for p in soup.find_all("p"):
            if p.text == "&#x200B;" or p.text == "\n\n":
                p.decompose()
        for a in soup.find_all("a"):
            if a.text == "[removed]":
                a.decompose()
            if a.get("href", "").find("preview.redd.it") != -1:
                img = soup.new_tag("img")
                img["src"] = a["href"]
                a.append(f"<p>{a.text}</p>")
                a.replace_with(img)
        self.content = str(soup)
        # resolve short text
        for tag in soup.find_all(["p", "span", "div"]):
            # add '\n' after the tag and then unwrap it
            tag.append("\n")
            tag.unwrap()
        for tag in soup.find_all(["strong"]):
            tag.replace_with(f"<b>{tag.text}</b>")
        self.text = str(soup)
        data = self.__dict__
        self.content = content_template.render(data=data)
        self.text = short_text_template.render(data=data)
        if get_html_text_length(self.text) < 800:
            self.message_type = MessageType.SHORT

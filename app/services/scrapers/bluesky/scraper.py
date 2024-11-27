from typing import Optional
from urllib.parse import urlparse

from atproto import AsyncClient, IdResolver, AtUri
from atproto_client.models.app.bsky.embed.record import ViewRecord
from atproto_client.models.app.bsky.feed.defs import ThreadViewPost, PostView

from app.config import JINJA2_ENV
from app.models.metadata_item import MediaFile, MessageType
from app.services.scrapers.scraper import Scraper, DataProcessor
from app.services.scrapers.bluesky import Bluesky
from app.services.scrapers.bluesky.config import BLUESKY_HOST, BLUESKY_MAX_LENGTH
from app.utils.logger import logger
from app.utils.parse import wrap_text_into_html

telegram_text_template = JINJA2_ENV.get_template("bluesky_telegram_text.jinja2")
content_template = JINJA2_ENV.get_template("bluesky_content.jinja2")


class BlueskyPost:
    def __init__(self, bluesky_url: str):
        self.url: str = bluesky_url
        bluesky_url_parser = urlparse(bluesky_url)
        self.bluesky_host: Optional[str] = bluesky_url_parser.netloc
        bluesky_path = bluesky_url_parser.path
        self.handle: Optional[str] = bluesky_path.split("/")[2]
        self.post_rkey: Optional[str] = bluesky_path.split("/")[-1]
        self.did: str = BlueskyScraper.id_resolver.handle.resolve(self.handle)


class BlueskyDataProcessor(DataProcessor):

    def __init__(self, url: str, bluesky_thread_data: ThreadViewPost):
        self.url: str = url
        self.bluesky_thread_data: ThreadViewPost = bluesky_thread_data
        logger.debug(
            f"BlueskyDataProcessor initialized with url: {url}\n and bluesky_thread_data: \n{bluesky_thread_data}")
        self._data: dict = {}

    async def get_item(self) -> dict:
        await self.process_data()
        bluesky_item = Bluesky.from_dict(self._data)
        return bluesky_item.to_dict()
        pass

    async def process_data(self):
        await self._resolve_thread_data()

    async def _resolve_thread_data(self) -> None:
        base_post_view_data = await BlueskyDataProcessor._resolve_single_post_data(self.bluesky_thread_data.post)
        base_post_view_data["url"] = self.url

        post_author_did = base_post_view_data["author_did"]

        parent_posts_text = ""
        parent_posts_content = ""
        parent_posts_media_files = []
        replies_posts_text = ""
        replies_posts_content = ""
        replies_posts_media_files = []
        # get post data from the parent posts whose author is the same as the base post author
        if self.bluesky_thread_data.parent:
            parent_posts_data = []
            parent_post_view = self.bluesky_thread_data.parent
            await BlueskyDataProcessor._get_parent_posts_data(parent_post_view, parent_posts_data)
            if parent_posts_data:
                for post_data in parent_posts_data:
                    parent_posts_text += "\n" + post_data["text"]
                    parent_posts_content += post_data["content"]
                    parent_posts_media_files.extend(post_data["media_files"])
        # get post data from the replies whose author is the same as the base post author
        if self.bluesky_thread_data.replies:
            replies_posts_data = []
            for post_thread_view in self.bluesky_thread_data.replies:
                post_view = post_thread_view.post
                if post_author_did == post_view.author.did:
                    post_data = await BlueskyDataProcessor._resolve_single_post_data(post_view)
                    replies_posts_data.append(post_data)
            if replies_posts_data:
                for post_data in replies_posts_data:
                    replies_posts_text += "\n" + post_data["text"]
                    replies_posts_content += post_data["content"]
                    replies_posts_media_files.extend(post_data["media_files"])
        base_post_view_data["text"] = parent_posts_text + base_post_view_data["text"] + replies_posts_text
        base_post_view_data["content"] = parent_posts_content + base_post_view_data["content"] + replies_posts_content
        base_post_view_data["media_files"] = parent_posts_media_files + base_post_view_data[
            "media_files"] + replies_posts_media_files

        if len(base_post_view_data["text"]) > BLUESKY_MAX_LENGTH:
            base_post_view_data["message_type"] = MessageType.LONG
        else:
            base_post_view_data["message_type"] = MessageType.SHORT

        self._data = base_post_view_data

    @staticmethod
    async def _get_parent_posts_data(parent_post_view: ThreadViewPost, parent_posts_data_list: list) -> None:
        parent_post_data = await BlueskyDataProcessor._resolve_single_post_data(parent_post_view.post)
        parent_posts_data_list.append(parent_post_data)
        if parent_post_view.parent:
            await BlueskyDataProcessor._get_parent_posts_data(parent_post_view.parent, parent_posts_data_list)

    @staticmethod
    async def _resolve_single_post_data(post_data: PostView) -> dict:
        at_uri = AtUri.from_str(post_data.uri)
        url = BLUESKY_HOST + "/profile/" + post_data.author.handle + "/post/" + at_uri.rkey
        author = post_data.author.display_name
        author_url = BLUESKY_HOST + "/profile/" + post_data.author.handle
        author_did = post_data.author.did
        text = post_data.record.text
        created_at = post_data.record.created_at

        parsed_post_data = {
            "url": url,
            "title": author + "\'s Bluesky post",
            "author": author,
            "author_url": author_url,
            "text": text,
            "category": "bluesky",
            "media_files": [],
            "created_at": created_at,
            "author_did": author_did,
        }

        media_files = []
        if post_data.embed is not None:
            # images and videos
            if "images" in post_data.embed.__dict__:
                for image in post_data.embed.images:
                    img_url = image.fullsize
                    img_item = {
                        "media_type": "image",
                        "url": img_url,
                        "caption": "",
                    }
                    media_files.append(img_item)
            # TODO: handle video, which is in m3u8 format that needs to be downloaded and converted to mp4
            parsed_post_data["media_files"] = media_files
            # retweet post
            if "record" in post_data.embed.__dict__ and post_data.embed.record is ViewRecord:
                retweet_post_data = await BlueskyDataProcessor._resolve_single_post_data(post_data.embed.record)
                parsed_post_data["retweet_post"] = retweet_post_data

        content = await BlueskyDataProcessor._generate_html_content(parsed_post_data)
        text = await BlueskyDataProcessor._generate_telegram_text(parsed_post_data)
        parsed_post_data["content"] = content
        parsed_post_data["text"] = text

        return parsed_post_data

    @staticmethod
    async def _generate_html_content(data: dict) -> str:
        html_content_text = wrap_text_into_html(data["text"])
        data["html_content_text"] = html_content_text
        content = content_template.render(data=data)
        return content

    @staticmethod
    async def _generate_telegram_text(data: dict) -> str:
        text = telegram_text_template.render(data=data)
        return text


class BlueskyScraper(Scraper):
    id_resolver = IdResolver()

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.client: AsyncClient = AsyncClient()
        self.username: Optional[str] = username
        self.password: Optional[str] = password
        self.did: Optional[str] = None

    async def init(self):
        if self.username and self.password:
            await self.client.login(self.username, self.password)
            # self.did = await self.client.com

    async def get_processor_by_url(self, url: str) -> BlueskyDataProcessor:
        bluesky_post = BlueskyPost(url)
        bluesky_post_data = await self._request_post_data(bluesky_post)
        return BlueskyDataProcessor(url, bluesky_post_data)

    async def _request_post_data(self, bluesky_post: BlueskyPost) -> ThreadViewPost:
        profile_identify = bluesky_post.did or bluesky_post.handle
        try:
            post_data = await self.client.get_post(profile_identify=profile_identify, post_rkey=bluesky_post.post_rkey)
            post_uri = post_data.uri
            post_thread_data = await self.client.get_post_thread(uri=post_uri)
            return post_thread_data.thread
        except Exception as e:
            logger.error(f"Error while getting post data: {e}")

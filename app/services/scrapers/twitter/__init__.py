# TODO: https://rapidapi.com/Glavier/api/twitter135
import asyncio
import traceback
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any, Tuple

import httpx
import jmespath

from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.utils.parse import get_html_text_length, wrap_text_into_html
from twitter.scraper import Scraper
from .config import (
    ALL_SCRAPER,
    ALL_SINGLE_SCRAPER,
    X_RAPIDAPI_HOST,
    SCRAPER_INFO,
    SHORT_LIMIT,
)
from app.config import X_RAPIDAPI_KEY, TWITTER_COOKIES, DEBUG_MODE
from app.utils.logger import logger


class Twitter(MetadataItem):
    def __init__(
            self,
            url: str,
            data: Optional[Any] = None,
            scraper: Optional[str] = "Twitter135",
            instruction: Optional[str] = "threads",
            **kwargs,
    ):
        # metadata fields
        self.url = url
        self.title = ""
        self.author = ""
        self.author_url = ""
        self.text = ""
        self.content = ""
        self.media_files: list[MediaFile] = []
        self.category = "twitter"
        self.message_type = MessageType.SHORT
        # auxiliary fields
        self.tid = urlparse(url).path.split("/")[-1]
        self.text_group = ""
        self.content_group = ""
        self.date = ""
        # reqeust fields
        self.instruction = instruction
        self.scraper = scraper
        self.host = ""
        self.headers = {}
        self.params = {}
        self.include_comments: bool = kwargs.get("include_comments", False)
        self.article_tweet: bool = False

    async def get_item(self) -> dict:
        await self.get_twitter()
        return self.to_dict()

    async def get_twitter(self) -> None:
        tweet_data = await self._get_response_tweet_data()
        self._process_tweet(tweet_data)

    async def _get_response_tweet_data(self) -> Dict:
        scrapers = ALL_SCRAPER if self.instruction == "threads" else ALL_SINGLE_SCRAPER
        for scraper in scrapers:
            self.scraper = scraper
            try:
                if self.scraper.startswith("Twitter"):
                    tweet_data = await self._rapidapi_get_response_tweet_data()
                    return tweet_data
                elif self.scraper == "api-client":
                    tweet_data = await self._api_client_get_response_tweet_data()
                    return tweet_data
            except Exception as e:
                logger.error(e)
                traceback.print_exc()
                continue
        raise Exception("No valid response from all Twitter scrapers")

    async def _rapidapi_get_response_tweet_data(self) -> Dict:
        async with httpx.AsyncClient() as client:
            self._get_request_headers()
            response = await client.get(
                url=self.host, headers=self.headers, params=self.params
            )
            if response.status_code == 200:
                tweet_data = response.json()
                if (
                        type(tweet_data) == dict
                        and ("errors" in tweet_data or "detail" in tweet_data)
                ) or (
                        type(tweet_data) == str
                        and ("400" in tweet_data or "429" in tweet_data)
                ):
                    raise Exception("Invalid response from Twitter API")
                else:
                    return tweet_data
            else:
                raise Exception("Invalid response from Twitter API")

    async def _api_client_get_response_tweet_data(self) -> Dict:
        scraper = Scraper(
            save=False,
            pbar=False,
            debug=0,
            cookies=TWITTER_COOKIES
        )
        tweet_data = await asyncio.to_thread(scraper.tweets_details, [int(self.tid)], limit=1)
        logger.debug(tweet_data)
        return tweet_data[0]

    def _process_tweet(self, tweet_data: Dict):
        # if self.scraper == "api-client":
        #     self.process_twitter_api_client(tweet_data)
        if self.scraper in ["api-client", "Twitter135"]:
            self._process_tweet_twitter135(tweet_data)
        elif self.scraper in ["Twitter154", "twitter-v24"]:
            self._process_tweet_Twitter154(tweet_data)

    def _process_tweet_twitter135(self, tweet_data: Dict):
        tweet_data_instructions = tweet_data["data"]["threaded_conversation_with_injections_v2"][
            "instructions"
        ]
        entries_instruction = next(
            (instr for instr in tweet_data_instructions if 'entries' in instr),
            None
        )
        entries = entries_instruction['entries']
        tweets = []
        for entry in entries:
            content = entry["content"]
            entry_type = content.get("entryType", "")

            if entry_type == "TimelineTimelineItem":
                item_content = content.get("itemContent", {})
                if item_content.get("itemType") == "TimelineTweet":
                    result = item_content.get("tweet_results", {}).get("result")
                    if result:
                        tweets.append(result)

            elif entry_type == "TimelineTimelineModule" and self.include_comments:
                for module_item in content.get("items", []):
                    item_content = module_item.get("item", {}).get("itemContent", {})
                    if item_content.get("itemType") == "TimelineTweet":
                        result = item_content.get("tweet_results", {}).get("result")
                        if result:
                            tweets.append(result)
        for tweet in tweets:
            if tweet["__typename"] == "TweetWithVisibilityResults":
                tweet = tweet["tweet"]
            parsed_tweet_data = self.parse_tweet_data_Twitter135(tweet)
            self.process_single_tweet_Twitter135(parsed_tweet_data)
        self.text += self.text_group
        self.text = self.text[:-1]
        self.content += self.content_group
        self.message_type = (
            MessageType.LONG if (get_html_text_length(self.text) > SHORT_LIMIT or self.article_tweet) else MessageType.SHORT
        )

    def process_single_tweet_Twitter135(self, tweet: Dict, retweeted=False) -> None:
        if tweet.get("tid") == self.tid:
            if tweet.get("article") and tweet["article"].get("title"):
                self.title = tweet["article"]["title"]
                self.article_tweet = True
            else:
                self.title = f"{tweet['name']}'s Tweet"
            self.author = tweet["name"]
            self.author_url = f"https://twitter.com/{tweet['username']}"
            self.date = tweet["date"]
        tweet_info = self.parse_single_tweet_Twitter135(tweet, retweeted=retweeted)
        self.text_group += tweet_info["text_group"]
        self.content_group += tweet_info["content_group"]
        self.media_files += tweet_info["media_files"]
        if tweet["quoted_tweet"]:
            retweeted_tweet_info = self.parse_tweet_data_Twitter135(
                tweet["quoted_tweet"]
            )
            self.process_single_tweet_Twitter135(retweeted_tweet_info, retweeted=True)
        if tweet.get("tid") == self.tid:
            self.content_group = self.content_group.replace("<hr>", "", 1)

    @staticmethod
    def parse_single_tweet_Twitter135(tweet: Dict, retweeted=False) -> Dict:
        tweet_info = {
            "media_files": [],
            "text_group": "",
            "content_group": "<hr>" if not retweeted else "<p>Quoted:</p>",
        }
        user_component = f"<a href='https://twitter.com/{tweet['username']}/status/{tweet['tid']}'>@{tweet['name']}</a>"

        if tweet.get("article"):
            article = tweet["article"]
            article_title = article.get("title", "")
            display_text = article_title if article_title else (
                tweet["full_text"] if tweet.get("full_text") else tweet["text"]
            )
            tweet_info["content_group"] += wrap_text_into_html(f"{user_component}: {display_text}")
            tweet_info["text_group"] += f"{user_component}: {display_text}\n"
            article_html, article_media = Twitter.parse_article_content(article)
            tweet_info["content_group"] += article_html
            tweet_info["media_files"] += article_media
        else:
            text = tweet["full_text"] if tweet.get("full_text") else tweet["text"]
            tweet_info["content_group"] += wrap_text_into_html(f"{user_component}: {text}")
            tweet_info["text_group"] += f"{user_component}: {text}\n"

        if tweet["media"]:
            for media in tweet["media"]:
                if media["type"] == "photo":
                    photo_url = media["media_url_https"] + "?name=orig"
                    tweet_info[
                        "content_group"
                    ] += f"<img src='{photo_url}'/>"
                    tweet_info["media_files"].append(
                        MediaFile(
                            media_type="image",
                            url=photo_url,
                            caption="",
                        )
                    )
                elif media["type"] == "video" or media["type"] == "animated_gif":
                    highest_bitrate_item = max(
                        media["video_info"]["variants"],
                        key=lambda x: x.get("bitrate", 0),
                    )
                    tweet_info[
                        "content_group"
                    ] += f'<video controls="controls" src="{highest_bitrate_item["url"]}"></video>'
                    tweet_info["media_files"].append(
                        MediaFile(
                            media_type="video",
                            url=highest_bitrate_item["url"],
                            caption="",
                        )
                    )
        tweet_info["content_group"] = tweet_info["content_group"].replace("\n", "<br>")
        return tweet_info

    @staticmethod
    def parse_tweet_data_Twitter135(data: Dict) -> Dict:
        result = jmespath.search(
            """{
            tid: rest_id,
            name: core.user_results.result.core.name || core.user_results.result.legacy.name,
            username: core.user_results.result.core.screen_name || core.user_results.result.legacy.screen_name,
            date: legacy.created_at,
            full_text: note_tweet.note_tweet_results.result.text,
            text: legacy.full_text,
            media: legacy.extended_entities.media,
            quoted_tweet: quoted_status_result.result,
            article: article.article_results.result
            }""",
            data,
        )
        return result

    def _process_tweet_Twitter154(self, tweet_data: Dict):
        pass

    @staticmethod
    def parse_article_content(article: Dict) -> Tuple[str, List[MediaFile]]:
        content_state = article.get("content_state", {})
        blocks = content_state.get("blocks", [])
        entity_map_list = content_state.get("entityMap", [])

        entity_lookup = {}
        for entry in entity_map_list:
            entity_lookup[str(entry["key"])] = entry["value"]

        html_parts = []
        media_files = []

        for block in blocks:
            block_type = block.get("type", "unstyled")
            text = block.get("text", "")
            inline_style_ranges = block.get("inlineStyleRanges", [])
            entity_ranges = block.get("entityRanges", [])

            if block_type == "atomic":
                for er in entity_ranges:
                    entity = entity_lookup.get(str(er["key"]))
                    if entity and entity.get("type") == "MEDIA":
                        for media_item in entity.get("data", {}).get("mediaItems", []):
                            media_id = media_item.get("mediaId", "")
                            media_url = _find_article_media_url(article, media_id)
                            if media_url:
                                html_parts.append(f"<img src='{media_url}'/>")
                                media_files.append(MediaFile(
                                    media_type="image",
                                    url=media_url,
                                    caption="",
                                ))
                continue

            styled_text = _apply_inline_formatting(
                text, inline_style_ranges, entity_ranges, entity_lookup
            )

            if block_type == "header-two":
                html_parts.append(f"<h2>{styled_text}</h2>")
            else:
                html_parts.append(f"<p>{styled_text}</p>")

        return "".join(html_parts), media_files

    def _get_request_headers(self):
        self.host = SCRAPER_INFO[self.scraper]["host"]
        self.headers = {
            "X-RapidAPI-Key": X_RAPIDAPI_KEY,
            "X-RapidAPI-Host": SCRAPER_INFO[self.scraper]["top_domain"]
                               + X_RAPIDAPI_HOST,
            "content-type": "application/octet-stream",
        }
        self.params = {
            SCRAPER_INFO[self.scraper]["params"]: self.tid,
        }


def _find_article_media_url(article: Dict, media_id: str) -> str:
    for entity in article.get("media_entities", []):
        if str(entity.get("media_id")) == str(media_id):
            media_info = entity.get("media_info", {})
            url = media_info.get("original_img_url", "")
            return url
    return ""


def _apply_inline_formatting(
        text: str,
        style_ranges: List[Dict],
        entity_ranges: List[Dict],
        entity_lookup: Dict,
) -> str:
    if not text or (not style_ranges and not entity_ranges):
        return text

    n = len(text)
    bold = [False] * n
    italic = [False] * n
    link_url = [None] * n

    for sr in style_ranges:
        start = sr["offset"]
        end = start + sr["length"]
        for i in range(start, min(end, n)):
            if sr["style"] == "Bold":
                bold[i] = True
            elif sr["style"] == "Italic":
                italic[i] = True

    for er in entity_ranges:
        entity = entity_lookup.get(str(er["key"]))
        if entity and entity.get("type") == "LINK":
            url = entity.get("data", {}).get("url", "")
            start = er["offset"]
            end = start + er["length"]
            for i in range(start, min(end, n)):
                link_url[i] = url

    result = []
    i = 0
    while i < n:
        cur_bold = bold[i]
        cur_italic = italic[i]
        cur_link = link_url[i]
        j = i
        while j < n and bold[j] == cur_bold and italic[j] == cur_italic and link_url[j] == cur_link:
            j += 1
        segment = text[i:j]
        if cur_bold:
            segment = f"<b>{segment}</b>"
        if cur_italic:
            segment = f"<i>{segment}</i>"
        if cur_link:
            segment = f"<a href='{cur_link}'>{segment}</a>"
        result.append(segment)
        i = j

    return "".join(result)

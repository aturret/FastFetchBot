# TODO: https://rapidapi.com/Glavier/api/twitter135

from urllib.parse import urlparse
from typing import Dict, Optional

import httpx
import jmespath

from app.models.metadata_item import MetadataItem, MediaFile, MessageType
from app.utils.parse import get_html_text_length
from .config import (
    ALL_SCRAPER,
    ALL_SINGLE_SCRAPER,
    X_RAPIDAPI_HOST,
    SCRAPER_INFO,
    SHORT_LIMIT,
)
from app.config import (
    X_RAPIDAPI_KEY,
)


class Twitter(MetadataItem):
    def __init__(
        self,
        url: str,
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
            self._get_request_headers()
            async with httpx.AsyncClient() as client:
                response = await client.get(url=self.host, headers=self.headers, params=self.params)
                if response.status_code == 200:
                    tweet_data = response.json()
                    if (type(tweet_data) == dict and ("errors" in tweet_data or "detail" in tweet_data)) or (
                        type(tweet_data) == str and ("400" in tweet_data or "429" in tweet_data)
                    ):
                        #  if the response is not valid, try next scraper
                        continue
                    else:
                        return tweet_data
                else:
                    continue
        raise Exception("No valid response from all Twitter scrapers")

    def _process_tweet(self, tweet_data: Dict):
        if self.scraper == "Twitter135":
            self.process_tweet_Twitter135(tweet_data)
        elif self.scraper in ["Twitter154", "twitter-v24"]:
            self.process_tweet_Twitter154(tweet_data)

    def process_tweet_Twitter135(self, tweet_data: Dict):
        entries = tweet_data["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"]
        tweets = []
        for i in entries:
            if (
                i["content"]["entryType"] == "TimelineTimelineItem"
                and i["content"]["itemContent"]["itemType"] == "TimelineTweet"
            ):
                tweets.append(i["content"]["itemContent"]["tweet_results"]["result"])
        for tweet in tweets:
            if tweet["__typename"] == "TweetWithVisibilityResults":
                tweet = tweet["tweet"]
            parsed_tweet_data = self.parse_tweet_data_Twitter135(tweet)
            self.process_single_tweet_Twitter135(parsed_tweet_data)
        self.text += self.text_group
        self.content += self.content_group
        self.message_type = "long" if get_html_text_length(self.text) > SHORT_LIMIT else "short"

    def process_single_tweet_Twitter135(self, tweet: Dict) -> None:
        if tweet["tid"] == self.tid:
            self.title = f"{tweet['name']}'s Tweet"
            self.author = tweet["name"]
            self.author_url = f"https://twitter.com/{tweet['username']}"
            self.date = tweet["date"]
        tweet_info = self.parse_single_tweet_Twitter135(tweet)
        self.text_group += tweet_info["text_group"]
        self.content_group += tweet_info["content_group"]
        self.media_files += tweet_info["media_files"]
        if tweet["quoted_tweet"] and tweet["tid"] == self.tid:
            self.process_single_tweet_Twitter135(tweet["quoted_tweet"])

    @staticmethod
    def parse_single_tweet_Twitter135(tweet: Dict) -> Dict:
        text = tweet["full_text"] if tweet["full_text"] else tweet["text"]
        tweet_info = {
            "media_files": [],
            "text_group": "",
            "content_group": "",
        }
        user_component = f"<a href='https://twitter.com/{tweet['username']}'>@{tweet['name']}</a>"
        tweet_info["content_group"] += f"<p>{user_component}: {text}</p>"
        tweet_info["text_group"] += f"{user_component}: {text}\n"
        if tweet["media"]:
            for media in tweet["media"]:
                if media["type"] == "photo":
                    tweet_info["content_group"] += f"<img src='{media['media_url_https']}'/>"
                    tweet_info["media_files"].append(
                        MediaFile(
                            media_type="image",
                            url=media["media_url_https"],
                            caption="",
                        )
                    )
                elif media["type"] == "video":
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
        tweet_info["content_group"] = tweet_info["content_group"].replace("\n", "<br>") + "<hr>"
        return tweet_info

    @staticmethod
    def parse_tweet_data_Twitter135(data: Dict) -> Dict:
        result = jmespath.search(
            """{
            tid: rest_id,
            name: core.user_results.result.legacy.name,
            username: core.user_results.result.legacy.screen_name,
            date: legacy.created_at,
            full_text: note_tweet.note_tweet_results.result.text,
            text: legacy.full_text,
            media: legacy.extended_entities.media,
            quoted_tweet: core.quoted_status_result.result
            }""",
            data,
        )
        return result

    def process_tweet_Twitter154(self, tweet_data: Dict):
        pass

    def _get_request_headers(self):
        self.host = SCRAPER_INFO[self.scraper]["host"]
        self.headers = {
            "X-RapidAPI-Key": X_RAPIDAPI_KEY,
            "X-RapidAPI-Host": SCRAPER_INFO[self.scraper]["top_domain"] + X_RAPIDAPI_HOST,
            "content-type": "application/octet-stream",
        }
        self.params = {
            SCRAPER_INFO[self.scraper]["params"]: self.tid,
        }

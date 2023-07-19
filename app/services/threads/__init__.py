import json
from typing import Dict
from urllib.parse import urlparse

import jmespath
from playwright.async_api import async_playwright

from app.utils.parse import get_html_text_length, unix_timestamp_to_utc

SHORT_LIMIT = 600


class Threads(object):
    def __init__(self, url: str, **kwargs):
        # metadata fields
        self.url = url
        self.title = ""
        self.author = ""
        self.author_url = ""
        self.text = ""
        self.content = ""
        self.media_files = []
        self.category = "Threads"
        self.type = "short"
        # auxiliary fields
        self.text_group = ""
        self.content_group = ""
        self.code = urlparse(url).path.split("/")[2]
        self.pics_url = []
        self.videos_url = []

    def to_dict(self):
        res = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Threads):
                res[k] = v.to_dict()
            else:
                res[k] = v
        return res

    async def get_threads(self):
        thread_data = await self.scrape_thread_data(self.url)
        self.process_threads_item(thread_data)
        print(thread_data)
        return self.to_dict()

    @staticmethod
    def parse_single_threads_data(data: Dict) -> Dict:
        """The code is referenced from https://scrapfly.io/blog/how-to-scrape-threads/"""
        """Parse Threads post JSON dataset for the most important fields"""
        result = jmespath.search(
            """{
            text: caption.text,
            published_on: taken_at,
            id: id,
            pk: pk,
            code: code,
            username: user.username,
            user_pic: user.profile_pic_url,
            user_verified: user.is_verified,
            user_pk: user.pk,
            user_id: user.id,
            has_audio: has_audio,
            reply_count: text_post_app_info.direct_reply_count,
            like_count: like_count,
            media_files: carousel_media[]
            images: carousel_media[].image_versions2.candidates[1].url,
            image: image_versions2.candidates[1].url,
            video: video_versions[1].url,
            media_count: carousel_media_count
            quoted_post: text_post_app_info.share_info.quoted_post
        }""",
            data,
        )
        return result

    async def scrape_thread_data(self, url: str) -> dict:
        """The code is referenced from https://scrapfly.io/blog/how-to-scrape-threads/"""
        """Scrape Threads post and replies from a given URL"""
        _xhr_calls = []

        def intercept_response(response):
            """capture all background requests and save them"""
            if response.request.resource_type == "xhr":
                _xhr_calls.append(response)
            return response

        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            page.on(
                "response", intercept_response
            )  # enable background request intercepting
            await page.goto(url)  # go to url and wait for the page to load
            await page.wait_for_selector(
                "[data-pressable-container=true]"
            )  # wait for page to finish loading
            # find all thread related background requests:
            gql_calls = [f for f in _xhr_calls if "/api/graphql" in f.url]
            thread_data = {
                "threads": [],
            }
            for xhr in gql_calls:
                data = json.loads(xhr.text())
                print(json.dumps(data, indent=4, ensure_ascii=False))
                threads = data["data"]["data"]["containing_thread"]["thread_items"]
                for thread in threads:
                    thread_data["threads"].append(
                        self.parse_single_threads_data(thread["post"])
                    )
            return thread_data

    def process_threads_item(self, thread_data: Dict) -> None:
        for thread in thread_data["threads"]:
            self.process_single_threads(thread)
        self.text += self.text_group
        self.content += self.content_group
        self.type = "long" if get_html_text_length(self.text) > SHORT_LIMIT else "short"

    def process_single_threads(self, thread: Dict) -> None:
        if thread["code"] == self.code:  # if the thread is the authoral post
            self.title = thread["username"] + "'s Threads"
            self.author = thread["username"]
            self.author_url = f"https://threads.net/@{thread['username']}"
            created_at = unix_timestamp_to_utc(thread["published_on"])
            reply_count = thread["reply_count"]
            like_count = thread["like_count"]
            self.content += f"<p>Created at: {created_at} "
            self.content += f" Reply count: {reply_count} "
            self.content += f" Like count: {like_count}</p>"
        thread_info = self.parse_single_threads(thread)
        self.text_group += thread_info["text_group"]
        self.content_group += thread_info["content_group"]
        self.pics_url += thread_info["pics_url"]
        self.videos_url += thread_info["videos_url"]
        self.media_files += thread_info["media_files"]

    @staticmethod
    def parse_single_threads(thread: Dict) -> Dict:
        thread_info = {
            "pics_url": [],
            "videos_url": [],
            "media_files": [],
            "text_group": "",
            "content_group": "",
        }
        # make html components, and solve the pictures and videos
        user_component = f"<a href='https://threads.net/@{thread['username']}'>@{thread['username']}</a>:"
        pics_component = ""
        videos_component = ""
        if not thread["media_count"]:  # if the thread doesn't have multiple media files
            if thread["video"]:  # if the threads has only one video/gif
                thread_info["videos_url"].append(thread["video"])
                thread_info["media_files"].append(
                    {"type": "video", "url": thread["video"], "caption": ""}
                )
                videos_component += (
                    f"<video controls=\"controls\" src=\"{thread['video']}\">"
                )
            elif thread["image"]:  # if the threads has only one picture
                thread_info["pics_url"].append(thread["image"])
                thread_info["media_files"].append(
                    {"type": "image", "url": thread["image"], "caption": ""}
                )
                pics_component += f"<img src=\"{thread['image']}\">"
        else:  # if the threads has more than one media files
            for media in thread["media_files"]:
                if len(media["video_versions"]) > 0:  # if the media is a video/gif
                    thread_info["videos_url"].append(media["video_versions"][0]["url"])
                    thread_info["media_files"].append(
                        {
                            "type": "video",
                            "url": media["video_versions"][0]["url"],
                            "caption": "",
                        }
                    )
                    videos_component += f"<video controls=\"controls\" src=\"{media['video_versions'][0]['url']}\">"
                else:  # if the media is a picture
                    thread_info["pics_url"].append(
                        media["image_versions2"]["candidates"][0]["url"]
                    )
                    thread_info["media_files"].append(
                        {
                            "type": "image",
                            "url": media["image_versions2"]["candidates"][0]["url"],
                            "caption": "",
                        }
                    )
                    pics_component += f"<img src=\"{media['image_versions2']['candidates'][0]['url']}\">"
        thread_info["text_group"] += user_component + thread["text"] + "\n"
        thread_info["content_group"] += (
                user_component
                + thread["text"].replace("\n", "<br>")
                + pics_component
                + videos_component
                + "<hr>"
        )
        if thread["quoted_post"] is not None:  # solve possible retweeted threads
            retweeted_thread = Threads.parse_single_threads_data(thread["quoted_post"])
            retweeted_thread_info = Threads.parse_single_threads(retweeted_thread)
            thread_info = {
                key: (thread_info[key] + retweeted_thread_info[key])
                for key in thread_info.keys()
                if key in retweeted_thread_info
            }
        return thread_info

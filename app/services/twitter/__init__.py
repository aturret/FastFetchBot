# TODO: https://rapidapi.com/Glavier/api/twitter135

from urllib.parse import urlparse, unquote
from typing import Dict, Optional

import jmespath

from app.models.metadata_item import MetadataItem
from .config import (
    ALL_SCRAPER,
    ALL_SINGLE_SCRAPER,
    X_RAPIDAPI_HOST,
    SCRAPER_INFO
)
from app.config import (
    X_RAPIDAPI_KEY,
)


class Twitter(MetadataItem):

    def __init__(self, url: str, scraper: Optional[str] = 'Twitter135', **kwargs):
        # metadata fields
        self.url = url
        self.title = ""
        self.author = ""
        self.author_url = ""
        self.text = ""
        self.content = ""
        self.media_files = []
        self.type = "long"
        # auxiliary fields
        self.tid = None
        self.text_group = ""
        self.content_group = ""
        self.code = ""
        self.pics_url = []
        self.videos_url = []
        # reqeust fields
        self.scraper = scraper
        self.host = ""
        self.headers = {}
        self.params = {}

    def get_request_headers_and_params(self):
        self.host = SCRAPER_INFO[self.scraper]["host"]
        self.headers = {
            "X-RapidAPI-Key": X_RAPIDAPI_KEY,
            "X-RapidAPI-Host": SCRAPER_INFO[self.scraper]["top_domain"] + X_RAPIDAPI_HOST,
            "content-type": "application/octet-stream",
        }
        self.params = {
            SCRAPER_INFO[self.scraper]["params"]: self.tid,
        }

    @staticmethod
    def parse_single_Twitter135_twitter_data(data: Dict) -> Dict:
        result = jmespath.search(
            """{
            
            }""",
            data, )
        return result


"""
scaper infos
"""

ALL_SCRAPER = ["Twitter135", "Twitter154", "twitter-v24"]
ALL_SINGLE_SCRAPER = ["Twitter154", "twitter-v24", "Twitter135"]
SCRAPER_INFO = {
    "Twitter135": {
        "host": "https://twitter135.p.rapidapi.com/v2/TweetDetail/",
        "top_domain": "twitter135",
        "params": "id"
    },
    "Twitter154": {
        "host": "https://twitter154.p.rapidapi.com/tweet/details/",
        "top_domain": "twitter154",
        "params": "tweet_id"
    },
    "twitter-v24": {
        "host": "https://twitter-v24.p.rapidapi.com/tweet/details",
        "top_domain": "twitter-v24",
        "params": "tweet_id"
    },
}
X_RAPIDAPI_HOST = ".p.rapidapi.com"

"""
twitter constants
"""

SHORT_LIMIT = 600

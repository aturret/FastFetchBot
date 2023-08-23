from fake_useragent import UserAgent

"""
patterns for check url type
"""
SOCIAL_MEDIA_WEBSITE_PATTERNS = {
    "weibo": [r"weibo\.com", r"m\.weibo\.cn"],
    "twitter": [r"twitter\.com", r"x\.com"],
    # "instagram": [r"instagram\.com"],
    "zhihu": [r"zhihu\.com"],
    "douban": [r"douban\.com"],
    "threads": [r"threads\.net"],
}
VIDEO_WEBSITE_PATTERNS = {
    "youtube": [r"youtube\.com", r"youtu\.be"],
    "bilibili": [r"bilibili\.com", r"b23\.tv"],
}

"""
default headers
"""
ua = UserAgent()
CHROME_USER_AGENT = ua.chrome
HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
}

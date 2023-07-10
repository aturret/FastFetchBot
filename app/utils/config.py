from fake_useragent import UserAgent

"""
patterns for check url type
"""
SOCIAL_MEDIA_WEBSITE_PATTERNS = {
    "weibo": [r"weibo\.com", r"m\.weibo\.cn"],
    "twitter": [r"twitter\.com"],
    "instagram": [r"instagram\.com"],
    "zhihu": [r"zhihu\.com"],
    "douban": [r"douban\.com"],
}
VIDEO_WEBSITE_PATTERNS = {
    "youtube": [r"youtube\.com", r"youtu\.be"],
    "bilibili": [r"bilibili\.com", r"b23\.tv"],
}

"""
fake user agent
"""
ua = UserAgent()
CHROME_USER_AGENT = ua.chrome

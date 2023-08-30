from fake_useragent import UserAgent

"""
patterns for check url type
"""
SOCIAL_MEDIA_WEBSITE_PATTERNS = {
    "weibo": [
        r"(m\.)?weibo.cn\/(status\/)?[0-9a-zA-Z]+",
        r"(www\.)?weibo\.com\/(status\/)?[0-9a-zA-Z]+",
    ],
    "twitter": [r"(twitter|x)\.com\/[^\/]+\/status\/[0-9]+"],
    "instagram": [r"(www\.)?instagram\.com\/(p|reel)\/[A-Za-z0-9_-]+"],
    "zhihu": [
        r"(www\.)?zhihu\.com\/question\/[0-9]+\/answer\/[0-9]+",
        r"(www\.)?zhihu\.com\/answer\/[0-9]+",
        r"(www\.)?zhihu\.com\/pin\/[0-9]+",
        r"zhuanlan\.zhihu\.com\/p\/[0-9]+",
    ],
    "douban": [
        r"(game|music|movie|book)?\.douban\.com\/review\/[0-9]+",
        r"((www|m)\.)?douban\.com\/note\/[0-9]+",
        r"((www|m)\.)?douban\.com\/people\/[^\/]+\/status\/[0-9]+",
        r"((www|m)\.)?douban\.com\/group\/topic\/[0-9]+",
        r"((www|m)\.)?douban\.com\/(game|music|movie|book)\/review\/[0-9]+",
    ],
    "threads": [
        r"(www\.)?threads\.net\/(@[a-zA-Z0-9]+\/post\/[A-Za-z0-9]+|t\/[A-Za-z0-9]+)\/"
    ],
}
VIDEO_WEBSITE_PATTERNS = {
    "youtube": [r"(((m|www)\.)youtube\.com\/watch)", r"youtu\.be\/[A-Za-z0-9_-]+"],
    "bilibili": [
        r"((www\.)?bilibili\.com\/video\/[A-Za-z0-9]+\/)",
        r"b23\.tv\/[A-Za-z0-9]+",
    ],
}

"""
default headers
"""
ua = UserAgent()
CHROME_USER_AGENT = ua.chrome
HEADERS = {
    "User-Agent": CHROME_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
}

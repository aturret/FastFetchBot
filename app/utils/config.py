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
    "wechat": [r"mp\.weixin\.qq\.com\/s", r"mp\.weixin\.qq\.com\/mp\/appmsg\/show"],
    "threads": [r"(www\.)?threads\.net\/@[a-zA-Z0-9]+\/post"],
    "xiaohongshu": [
        r"(www\.)?xiaohongshu\.com\/(discovery\/item|explore)\/[0-9a-zA-Z_-]+",
        r"(www\.)?xhslink\.com\/[0-9a-zA-Z_-]+",
    ],
    "reddit": [r"(www\.)?reddit\.com\/r\/[a-zA-Z0-9_-]+\/comments\/[a-zA-Z0-9_-]+"],
}
VIDEO_WEBSITE_PATTERNS = {
    "youtube": [
        r"((m|www)\.)youtube\.com\/watch",
        r"youtu\.be\/[A-Za-z0-9_-]+",
        r"youtube\.com\/shorts\/[A-Za-z0-9_-]+",
    ],
    "bilibili": [
        r"((www\.)?bilibili\.com\/video\/[A-Za-z0-9]+)",
        r"b23\.tv\/[A-Za-z0-9]+",
    ],
}

"""
set variables for functions
"""
HTTPS_URL_REGEX = r"(http|https)://([\w.!@#$%^&*()_+-=])*\s*"

"""
patterns for check url type
"""
WEBSITE_PATTERNS = {
    "weibo": [r"weibo\.com", r"m\.weibo\.cn"],
    "twitter": [r"twitter\.com"],
    "instagram": [r"instagram\.com"],
    "youtube": [r"youtube\.com", r"youtu\.be"],
    "bilibili": [r"bilibili\.com", r"b23\.tv"],
    "zhihu": [r"zhihu\.com"],
    "douban": [r"douban\.com"],
}

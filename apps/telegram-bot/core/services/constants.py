"""
set variables for functions
"""
HTTPS_URL_REGEX = r"(http|https)://([\w.!@#$%^&*()_+-=])*\s*"

"""
telegram bot api constants
"""
TELEGRAM_SINGLE_MESSAGE_MEDIA_LIMIT = 10
TELEGRAM_TEXT_LIMIT = 900
TELEGRAM_FILE_UPLOAD_LIMIT = 52428800  # 50MB
TELEGRAM_FILE_UPLOAD_LIMIT_LOCAL_API = 2147483648  # 2GB

"""
function constants
"""
REFERER_REQUIRED = ["douban", "weibo"]

"""
template translation(just a workaround)
"""
TEMPLATE_TRANSLATION = {
    "en": {
        "online_snapshot": "Online Snapshot",
        "original_webpage": "Original Webpage",
    },
    "zh_CN": {
        "online_snapshot": "原文备份",
        "original_webpage": "阅读原文",
    },
    "zh_TW": {
        "online_snapshot": "原文備份",
        "original_webpage": "閱讀原文",
    },
}


def template_translation(key: str, language: str = "zh_CN") -> str:
    lang_dict = TEMPLATE_TRANSLATION.get(language, TEMPLATE_TRANSLATION["zh_CN"])
    return lang_dict.get(key, key)

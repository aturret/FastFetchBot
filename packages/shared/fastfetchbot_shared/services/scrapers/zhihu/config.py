from fastfetchbot_shared.services.scrapers.config import settings, ZHIHU_COOKIES_JSON

SHORT_LIMIT = 600
ZHIHU_COLUMNS_API_HOST = "https://zhuanlan.zhihu.com/api"
ZHIHU_COLUMNS_API_HOST_V2 = "https://api.zhihu.com/article/"
ZHIHU_API_HOST = "https://www.zhihu.com/api/v4"
ZHIHU_API_ANSWER_PARAMS = "include=content,excerpt,voteup_count,comment_count,question.detail"
ZHIHU_HOST = "https://www.zhihu.com"
ALL_METHODS = ["api", "fxzhihu"]
"""
Methods: "api" calls Zhihu API v4 directly (ported from FxZhihu), "fxzhihu" calls external FxZhihu server as fallback.
The "json" method parses HTML script tags, "html" parses page content directly.
"""

# Cookie for direct API calls: prefer ZHIHU_Z_C0 env var, fall back to cookies JSON
if settings.ZHIHU_Z_C0:
    ZHIHU_API_COOKIE = f"z_c0={settings.ZHIHU_Z_C0}"
elif ZHIHU_COOKIES_JSON:
    ZHIHU_API_COOKIE = ';'.join(f"{cookie['name']}={cookie['value']}" for cookie in ZHIHU_COOKIES_JSON)
else:
    ZHIHU_API_COOKIE = None

# Full cookie string for HTML/JSON methods and fxzhihu fallback
if ZHIHU_COOKIES_JSON:
    ZHIHU_COOKIES = ';'.join(f"{cookie['name']}={cookie['value']}" for cookie in ZHIHU_COOKIES_JSON)
else:
    ZHIHU_COOKIES = None

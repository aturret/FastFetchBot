from fastfetchbot_shared.services.scrapers.config import settings, ZHIHU_COOKIES_JSON

SHORT_LIMIT = 600
ZHIHU_COLUMNS_API_HOST = "https://zhuanlan.zhihu.com/api"
ZHIHU_COLUMNS_API_HOST_V2 = "https://api.zhihu.com/article/"
ZHIHU_API_HOST = "https://www.zhihu.com/api/v4"
ZHIHU_API_ANSWER_PARAMS = "include=content,excerpt,voteup_count,comment_count,question.detail"
ZHIHU_HOST = "https://www.zhihu.com"
ZHIHU_DAILY_API = "https://daily.zhihu.com/api/7/story"
ALL_METHODS = ["api", "signed_api", "fxzhihu"]
"""
Methods, tried in this order (when the cookie has d_c0, "signed_api" moves to the front):
- "api" calls Zhihu API v4 directly with the z_c0 cookie (ported from FxZhihu).
- "signed_api" calls the same endpoints with an x-zse-96 signature (needs d_c0 in the cookie).
- "fxzhihu" calls the external FxZhihu server as the last fallback.
The "json" method parses HTML script tags, "html" parses page content directly.
"""

# One cookie for every request method, resolved in this order:
# 1. ZHIHU_Z_C0 (+ ZHIHU_D_C0) env vars: the two fields Zhihu actually needs.
#    z_c0 is the login token; d_c0 is only needed by the signed_api method.
# 2. Otherwise every cookie exported to conf/zhihu_cookies.json.
if settings.ZHIHU_Z_C0:
    ZHIHU_COOKIES = f"z_c0={settings.ZHIHU_Z_C0}"
    if settings.ZHIHU_D_C0:
        ZHIHU_COOKIES += f"; d_c0={settings.ZHIHU_D_C0}"
elif ZHIHU_COOKIES_JSON:
    ZHIHU_COOKIES = ';'.join(f"{cookie['name']}={cookie['value']}" for cookie in ZHIHU_COOKIES_JSON)
else:
    ZHIHU_COOKIES = None

# Backward-compatible alias; same value as ZHIHU_COOKIES.
ZHIHU_API_COOKIE = ZHIHU_COOKIES

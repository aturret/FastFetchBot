from app.config import ZHIHU_COOKIES_JSON

SHORT_LIMIT = 600
ZHIHU_COLUMNS_API_HOST = "https://zhuanlan.zhihu.com/api"
ZHIHU_API_HOST = "https://www.zhihu.com/api/v4"
ZHIHU_API_ANSWER_PARAMS = ("include=content%2Cexcerpt%2Cauthor%2Cvoteup_count%2Ccomment_count%2Cquestion%2Ccreated_time"
                    "%2Cquestion.detail")
ZHIHU_HOST = "https://www.zhihu.com"
ALL_METHODS = ["api", "json", "html"]
"""
There are three methods to get zhihu item: from zhihu v4 api(api), a json object in the html script(json),
 or parsing the html page content directly.
 For most occasions, the api method is the best choice. But Zhihu official api only opens for status and article.
 Therefore, we must use the json method to get the answer. And if one of the above two methods fails, the get_item method
 would try to parse the html page content directly.
 You can also pass the method as a parameter when initializing the Zhihu object. If not, the default method is api.
"""

if ZHIHU_COOKIES_JSON:
    ZHIHU_COOKIES = ';'.join(f"{cookie['name']}={cookie['value']}" for cookie in ZHIHU_COOKIES_JSON)
else:
    ZHIHU_COOKIES = None

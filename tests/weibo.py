from typing import Optional, Union

from tests.common import AsyncTestBase
from app.services.weibo import Weibo
from .cases.weibo import weibo_cases


class WeiboTestBase(AsyncTestBase):
    weibo: Optional[Weibo] = None

    async def get_weibo(self, url: str, **kwargs):
        self.weibo = Weibo(url=url, **kwargs)
        self.weibo_result = await self.weibo.get_weibo()
        print(self.weibo_result)

    def assert_value_not_none(self):
        for k, v in self.weibo_result.items():
            self.assertIsNotNone(v, msg=f"{k} is None")


class GetWeiboTest(WeiboTestBase):

    async def test_pure_short_text(self):
        for url in weibo_cases["pure_short_text"]:
            await self.get_weibo(url)
            self.assert_value_not_none()

    async def test_pure_long_text(self):
        for url in weibo_cases["pure_long_text"]:
            await self.get_weibo(url)
            self.assert_value_not_none()

    async def test_single_video_short_text(self):
        for url in weibo_cases["single_video_short_text"]:
            await self.get_weibo(url)
            self.assert_value_not_none()

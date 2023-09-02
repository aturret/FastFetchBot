from typing import Dict

from playwright.async_api import async_playwright

from app.models.metadata_item import MetadataItem
from app.utils.config import CHROME_USER_AGENT
from app.config import XIAOHONGSHU_COOKIES


class Xiaohongshu(MetadataItem):
    def __init__(self, url):
        self.url = url

    async def get_item(self) -> dict:
        await self.get_xiaohongshu()
        return self.to_dict()

    async def get_xiaohongshu(self) -> None:
        pass

    async def _scrape_page(self) -> Dict:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=CHROME_USER_AGENT
            )
            await context.add_cookies([{
                'name': "web_session",
                'value': XIAOHONGSHU_COOKIES['web_session'],
                'domain': ".xiaohongshu.com",
                'path': "/"
            }])
            page = await context.new_page()

    async def _login_by_cookies(self) -> None:
        pass

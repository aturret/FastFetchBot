import asyncio
import functools
import sys
from typing import Optional

# import redis
from playwright.async_api import BrowserContext, Page
from tenacity import RetryError, retry, retry_if_result, stop_after_attempt, wait_fixed

from fastfetchbot_shared.utils.logger import logger

# import config
from .base_crawler import AbstractLogin
from . import utils


class XHSLogin(AbstractLogin):
    def __init__(
        self,
        login_type: str,
        browser_context: BrowserContext,
        context_page: Page,
        login_phone: Optional[str] = "",
        cookie_str: dict = {},
    ):
        self.login_type = login_type
        self.browser_context = browser_context
        self.context_page = context_page
        self.login_phone = login_phone
        self.cookie_str = cookie_str

    @retry(
        stop=stop_after_attempt(20),
        wait=wait_fixed(1),
        retry=retry_if_result(lambda value: value is False),
    )
    async def check_login_state(self, no_logged_in_session: str) -> bool:
        """
        Check if the current login status is successful and return True otherwise return False
        retry decorator will retry 20 times if the return value is False, and the retry interval is 1 second
        if max retry times reached, raise RetryError
        """
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = utils.convert_cookies(current_cookie)
        current_web_session = cookie_dict.get("web_session")
        if current_web_session != no_logged_in_session:
            return True
        return False

    async def begin(self):
        """Start login xiaohongshu"""
        logger.info("Begin login xiaohongshu ...")
        if self.login_type == "qrcode":
            await self.login_by_qrcode()
        elif self.login_type == "phone":
            await self.login_by_mobile()
        elif self.login_type == "cookie":
            await self.login_by_cookies()
        else:
            raise ValueError(
                "Invalid Login Type Currently only supported qrcode or phone or cookies ..."
            )

    async def login_by_mobile(self):
        pass

    async def login_by_qrcode(self):
        """login xiaohongshu website and keep webdriver login state"""
        logger.info("Begin login xiaohongshu by qrcode ...")
        # login_selector = "div.login-container > div.left > div.qrcode > img"
        qrcode_img_selector = "xpath=//img[@class='qrcode-img']"
        # find login qrcode
        base64_qrcode_img = await utils.find_login_qrcode(
            self.context_page, selector=qrcode_img_selector
        )
        if not base64_qrcode_img:
            logger.info("login failed , have not found qrcode please check ....")
            # if this website does not automatically popup login dialog box, we will manual click login button
            await asyncio.sleep(0.5)
            login_button_ele = self.context_page.locator(
                "xpath=//*[@id='app']/div[1]/div[2]/div[1]/ul/div[1]/button"
            )
            await login_button_ele.click()
            base64_qrcode_img = await utils.find_login_qrcode(
                self.context_page, selector=qrcode_img_selector
            )
            if not base64_qrcode_img:
                sys.exit()

        # get not logged session
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = utils.convert_cookies(current_cookie)
        no_logged_in_session = cookie_dict.get("web_session")

        # show login qrcode
        # fix issue #12
        # we need to use partial function to call show_qrcode function and run in executor
        # then current asyncio event loop will not be blocked
        partial_show_qrcode = functools.partial(utils.show_qrcode, base64_qrcode_img)
        asyncio.get_running_loop().run_in_executor(
            executor=None, func=partial_show_qrcode
        )

        logger.info(f"waiting for scan code login, remaining time is 20s")
        try:
            await self.check_login_state(no_logged_in_session)
        except RetryError:
            logger.info("Login xiaohongshu failed by qrcode login method ...")
            sys.exit()

        wait_redirect_seconds = 5
        logger.info(
            f"Login successful then wait for {wait_redirect_seconds} seconds redirect ..."
        )
        await asyncio.sleep(wait_redirect_seconds)

    async def login_by_cookies(self):
        """login xiaohongshu website by cookies"""
        logger.info("Begin login xiaohongshu by cookie ...")
        for key, value in self.cookie_str.items():
            if key != "web_session":  # only set web_session cookie attr
                continue
            await self.browser_context.add_cookies(
                [
                    {
                        "name": key,
                        "value": value,
                        "domain": ".xiaohongshu.com",
                        "path": "/",
                    }
                ]
            )

import base64
import logging
import os
import random
import re
import time
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from PIL import Image, ImageDraw
from playwright.async_api import Cookie, Page


async def find_login_qrcode(page: Page, selector: str) -> str:
    """find login qrcode image from target selector"""
    try:
        elements = await page.wait_for_selector(
            selector=selector,
        )
        login_qrcode_img = await elements.get_property("src")  # type: ignore
        return str(login_qrcode_img)

    except Exception as e:
        print(e)
        return ""


def show_qrcode(qr_code) -> None:  # type: ignore
    """parse base64 encode qrcode image and show it"""
    qr_code = qr_code.split(",")[1]
    qr_code = base64.b64decode(qr_code)
    image = Image.open(BytesIO(qr_code))

    # Add a square border around the QR code and display it within the border to improve scanning accuracy.
    width, height = image.size
    new_image = Image.new("RGB", (width + 20, height + 20), color=(255, 255, 255))
    new_image.paste(image, (10, 10))
    draw = ImageDraw.Draw(new_image)
    draw.rectangle((0, 0, width + 19, height + 19), outline=(0, 0, 0), width=1)
    new_image.show()


def get_user_agent() -> str:
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.79 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
    ]
    return random.choice(ua_list)


def convert_cookies(cookies: Optional[List[Cookie]]) -> Tuple[str, Dict]:
    if not cookies:
        return "", {}
    cookies_str = ";".join(
        [f"{cookie.get('name')}={cookie.get('value')}" for cookie in cookies]
    )
    cookie_dict = dict()
    for cookie in cookies:
        cookie_dict[cookie.get("name")] = cookie.get("value")
    return cookies_str, cookie_dict


def convert_str_cookie_to_dict(cookie_str: str) -> Dict:
    cookie_dict: Dict[str, str] = dict()
    if not cookie_str:
        return cookie_dict
    for cookie in cookie_str.split(";"):
        cookie = cookie.strip()
        if not cookie:
            continue
        cookie_list = cookie.split("=")
        if len(cookie_list) != 2:
            continue
        cookie_value = cookie_list[1]
        if isinstance(cookie_value, list):
            cookie_value = "".join(cookie_value)
        cookie_dict[cookie_list[0]] = cookie_value
    return cookie_dict


def get_current_timestamp():
    return int(time.time() * 1000)


def match_interact_info_count(count_str: str) -> int:
    if not count_str:
        return 0

    match = re.search(r"\d+", count_str)
    if match:
        number = match.group()
        return int(number)
    else:
        return 0


def init_loging_config():
    level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s ",
        datefmt="%Y-%m-%d  %H:%M:%S",
    )
    _logger = logging.getLogger("MediaCrawler")
    _logger.setLevel(level)
    return _logger


logger = init_loging_config()


def get_track_simple(distance) -> List[int]:
    track: List[int] = []
    current = 0
    mid = distance * 4 / 5
    t = 0.2
    v = 1

    while current < distance:
        if current < mid:
            a = 4
        else:
            a = -3
        v0 = v
        v = v0 + a * t  # type: ignore
        move = v0 * t + 1 / 2 * a * t * t
        current += move  # type: ignore
        track.append(round(move))
    return track


def get_tracks(distance: int, level: str = "easy") -> List[int]:
    if level == "easy":
        return get_track_simple(distance)
    else:
        from . import easing

        _, tricks = easing.get_tracks(distance, seconds=2, ease_func="ease_out_expo")
        return tricks

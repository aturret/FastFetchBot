import uuid
import httpx
import traceback

from lxml import etree

from app.models.classes import NamedBytesIO
from app.utils.config import CHROME_USER_AGENT, HEADERS


async def get_response(url: str, headers: dict = None) -> httpx.Response:
    if headers is None:
        headers = HEADERS
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        return resp


async def get_response_json(url: str, headers=None) -> dict:
    try:
        response = await get_response(url, headers)
        json_result = response.json()
    except Exception as e:
        print(e, traceback.format_exc())
        json_result = None
    return json_result


async def get_selector(url: str, headers: dict) -> etree.HTML:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=30)
        if resp.history:
            print("Request was redirected")
            for resp in resp.history:
                print(resp.status_code, resp.url)
            print("Final destination:")
            print(resp.status_code, resp.url)
        selector = etree.HTML(resp.content)
        return selector


async def download_a_iobytes_file(
    url, file_name=None, headers=None, referer=None
) -> NamedBytesIO:
    if headers is None:
        headers = HEADERS
    if referer is not None:
        headers["referer"] = referer
    async with httpx.AsyncClient() as client:
        response = await client.get(url=url, headers=headers)
    file_data = response.content
    if file_name is None:
        file_format = url.split(".")[-1]
        file_name = "media-" + str(uuid.uuid1())[:8] + "." + file_format
    io_object = NamedBytesIO(file_data, name=file_name)
    return io_object

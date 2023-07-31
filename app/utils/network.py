import uuid
import httpx
import traceback

from lxml import etree

from app.models.classes import NamedBytesIO
from app.utils.config import CHROME_USER_AGENT, HEADERS
from app.config import HTTP_REQUEST_TIMEOUT


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
    """
    A function to get etree.HTML selector according to url and headers.
    We can use this function to do additional parsing works.
    :param url: the target webpage url
    :param headers: the headers of the request
    :return: the selector of the target webpage parsed by etree.HTML
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=HTTP_REQUEST_TIMEOUT)
        if resp.history:  # if there is a redirect, the request will have a response chain
            print("Request was redirected")
            for resp in resp.history:
                print(resp.status_code, resp.url)
            print("Final destination:", resp.status_code, resp.url)
        selector = etree.HTML(resp.content)  # the content of the final destination
        return selector


async def download_a_iobytes_file(url, file_name=None, file_format=None, headers=None, referer=None) -> NamedBytesIO:
    """
    A customized function to download a file from url and return a NamedBytesIO object.
    :param url:
    :param file_name:
    :param headers:
    :param referer:
    :return:
    """
    if headers is None:
        headers = HEADERS
    if referer is not None:
        headers["referer"] = referer
    async with httpx.AsyncClient() as client:
        response = await client.get(url=url, headers=headers, timeout=HTTP_REQUEST_TIMEOUT)
    file_data = response.content
    if file_name is None:
        file_format = file_format if file_format else url.split(".")[-1]
        file_name = "media-" + str(uuid.uuid1())[:8] + "." + file_format
    io_object = NamedBytesIO(file_data, name=file_name)
    return io_object

import datetime
import os
import uuid

import aiofiles
import httpx
import traceback

from lxml import etree

from app.models.classes import NamedBytesIO
from app.utils.config import CHROME_USER_AGENT, HEADERS
from app.config import HTTP_REQUEST_TIMEOUT, DOWNLOAD_DIR
from app.utils.image import check_image_type
from app.utils.logger import logger


async def get_response(
    url: str, headers: dict = None, params: dict = None
) -> httpx.Response:
    if headers is None:
        headers = HEADERS
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url, headers=headers, params=params, timeout=HTTP_REQUEST_TIMEOUT
        )
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
        resp = await client.get(
            url, headers=headers, follow_redirects=True, timeout=HTTP_REQUEST_TIMEOUT
        )
        if (
            resp.history
        ):  # if there is a redirect, the request will have a response chain
            print("Request was redirected")
            for h in resp.history:
                print(h.status_code, h.url)
            print("Final destination:", resp.status_code, resp.url)
        selector = etree.HTML(resp.text)  # the content of the final destination
        return selector


async def download_file_by_metadata_item(
    url: str,
    data: dict,
    file_name: str = None,
    file_format: str = None,
    headers: dict = None,
) -> NamedBytesIO:
    """
    A customized function to download a file from url and return a NamedBytesIO object.
    :param file_format:
    :param data:
    :param url:
    :param file_name:
    :param headers:
    :return:
    """
    try:
        if headers is None:
            headers = HEADERS
        headers["referer"] = data["url"]
        if data["category"] in ["reddit"]:
            headers["Accept"] = "image/avif,image/webp,*/*"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url=url, headers=headers, timeout=HTTP_REQUEST_TIMEOUT
            )
        file_data = response.content
        if file_name is None:
            file_format = file_format if file_format else url.split(".")[-1]
            file_name = "media-" + str(uuid.uuid1())[:8] + "." + file_format
        io_object = NamedBytesIO(file_data, name=file_name)
        return io_object
    except Exception as e:
        logger.error(f"Failed to download {url}, {e}")
        raise e


async def download_file_to_local(
    url: str,
    file_path: str = None,
    dir_path: str = DOWNLOAD_DIR,
    file_name: str = "",
    headers: dict = None,
    referer: str = None,
) -> str:
    io_object = await download_file_by_metadata_item(
        url=url, file_name=file_name, headers=headers, referer=referer
    )
    ext = await check_image_type(io_object)
    io_object.seek(0)
    file_name = file_name + uuid.uuid4().hex + "." + ext
    logger.info(f"Downloading {file_name}")
    if file_path is None and dir_path is not None:
        file_path = os.path.join(dir_path, file_name)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(io_object.read())
    return file_path

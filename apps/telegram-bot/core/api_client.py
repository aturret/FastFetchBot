import httpx
from core.config import API_SERVER_URL, API_KEY, API_KEY_NAME
from fastfetchbot_shared.utils.logger import logger


async def get_item(url: str, ban_list: list = None, **kwargs) -> dict:
    """Call API server's /scraper/getItem endpoint."""
    params = {"url": url, API_KEY_NAME: API_KEY}
    params.update(kwargs)
    if ban_list:
        params["ban_list"] = ",".join(ban_list)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_SERVER_URL}/scraper/getItem",
            params=params,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()


async def get_url_metadata(url: str, ban_list: list = None) -> dict:
    """Call API server's /scraper/getUrlMetadata endpoint."""
    params = {"url": url, API_KEY_NAME: API_KEY}
    if ban_list:
        params["ban_list"] = ",".join(ban_list)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_SERVER_URL}/scraper/getUrlMetadata",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

import httpx
from core.config import settings
from fastfetchbot_shared.utils.logger import logger


async def get_item(url: str, ban_list: list = None, **kwargs) -> dict:
    """Call API server's /scraper/getItem endpoint."""
    params = {"url": url, settings.API_KEY_NAME: settings.API_KEY}
    params.update(kwargs)
    if ban_list:
        params["ban_list"] = ",".join(ban_list)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.API_SERVER_URL}/scraper/getItem",
            params=params,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()


async def get_url_metadata(url: str, ban_list: list = None) -> dict:
    """Call API server's /scraper/getUrlMetadata endpoint."""
    params = {"url": url, settings.API_KEY_NAME: settings.API_KEY}
    if ban_list:
        params["ban_list"] = ",".join(ban_list)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.API_SERVER_URL}/scraper/getUrlMetadata",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

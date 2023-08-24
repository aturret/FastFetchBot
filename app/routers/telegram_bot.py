from fastapi import APIRouter
from fastapi.requests import Request

from app.services.telegram_bot import set_webhook, process_telegram_update
from app.config import TELEGRAM_WEBHOOK_URL
from app.utils.logger import logger
from fastapi import Security
from app.auth import verify_api_key, verify_telegram_api_key

router = APIRouter(prefix="/telegram")


@router.post("/bot/webhook", dependencies=[Security(verify_telegram_api_key)])
async def telegram_bot_webhook(request: Request):
    # TODO: add security check
    data = await request.json()
    await process_telegram_update(data)
    return "ok"


@router.get("/bot/set_webhook", dependencies=[Security(verify_api_key)])
async def telegram_bot_set_webhook():
    # TODO: add security check, fix URL
    logger.debug(f"set telegram webhook: {TELEGRAM_WEBHOOK_URL}")
    await set_webhook(TELEGRAM_WEBHOOK_URL)
    return "ok"

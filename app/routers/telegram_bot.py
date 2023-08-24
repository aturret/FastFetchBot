from fastapi import APIRouter
from fastapi.requests import Request

from app.services.telegram_bot import set_webhook, process_telegram_update
from app.config import TELEGRAM_WEBHOOK_URL, API_KEY_NAME, TELEGRAM_API_KEY
from app.utils.logger import logger
from fastapi import Security
from app.auth import verify_api_key, verify_telegram_api_key

router = APIRouter(prefix="/telegram")


@router.post("/bot/webhook", dependencies=[Security(verify_telegram_api_key)])
async def telegram_bot_webhook(request: Request):
    data = await request.json()
    await process_telegram_update(data)
    return "ok"


@router.get("/bot/set_webhook", dependencies=[Security(verify_api_key)])
async def telegram_bot_set_webhook():
    # mask api key
    logger.debug(
        f"set telegram webhook: {TELEGRAM_WEBHOOK_URL}?{API_KEY_NAME}={TELEGRAM_API_KEY[:2]}{'*' * (len(TELEGRAM_API_KEY) - 4)}{TELEGRAM_API_KEY[-2:]}"
    )
    await set_webhook(f"{TELEGRAM_WEBHOOK_URL}?{API_KEY_NAME}={TELEGRAM_API_KEY}")
    return "ok"

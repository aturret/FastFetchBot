import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.requests import Request

from app.services.telegram_bot import set_webhook, process_telegram_update
from app.config import TELEGRAM_WEBHOOK_URL, TELEGRAM_BOT_SECRET_TOKEN
from app.utils.logger import logger
from fastapi import Security, BackgroundTasks
from app.auth import verify_api_key, verify_telegram_api_header

router = APIRouter(prefix="/telegram")


@router.post("/bot/webhook", dependencies=[Security(verify_telegram_api_header)])
async def telegram_bot_webhook(request: Request, background_tasks: BackgroundTasks):
    logger.debug("A telegram bot webhook received")
    data = await request.json()
    background_tasks.add_task(process_telegram_update, data)
    logger.debug(f"telegram bot webhook data received, background task added: {data}")
    return "ok"


@router.get("/bot/set_webhook", dependencies=[Security(verify_api_key)])
async def telegram_bot_set_webhook():
    # mask api key
    logger.debug(
        f"set telegram webhook: {TELEGRAM_WEBHOOK_URL}\nsecret token: {TELEGRAM_BOT_SECRET_TOKEN[:2]}{'*' * (len(TELEGRAM_BOT_SECRET_TOKEN) - 4)}{TELEGRAM_BOT_SECRET_TOKEN[-2:]}"
    )
    if await set_webhook():
        return "ok"
    else:
        logger.error("set telegram webhook failed")
        raise HTTPException(status_code=500, detail="set telegram webhook failed") 

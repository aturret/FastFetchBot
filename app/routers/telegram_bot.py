from fastapi import APIRouter
from fastapi.requests import Request

from app.services.telegram_bot.__init__ import set_webhook, process_telegram_update
from app.config import WEBHOOK_URL


router = APIRouter(prefix="/telegram")


@router.post("/bot/webhook")
async def telegram_bot_webhook(request: Request):
    # TODO: add security check
    data = await request.json()
    await process_telegram_update(data)
    return "ok"


@router.get("/bot/set_webhook")
async def telegram_bot_set_webhook():
    # TODO: add security check, fix URL
    print("WEBHOOK_URL", WEBHOOK_URL)
    await set_webhook(WEBHOOK_URL)
    return "ok"

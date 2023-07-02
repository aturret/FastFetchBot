from fastapi import APIRouter
from fastapi.requests import Request

from app.services.telegram_bot import set_webhook

router = APIRouter(prefix="/telegram")


@router.post("/bot/webhook")
async def telegram_bot_webhook(request: Request):
    # TODO: add security check
    data = await request.json()
    # process_telegram_event(data)
    return "ok"


@router.get("/bot/set_webhook")
async def telegram_bot_set_webhook():
    # TODO: add security check, fix URL
    return await set_webhook("")

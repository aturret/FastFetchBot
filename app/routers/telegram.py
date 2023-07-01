from fastapi import APIRouter
from fastapi.requests import Request

router = APIRouter(prefix='/telegram')

@router.post("/bot")
async def telegram_bot_webhook(request: Request):
    # TODO: add security check
    data = await request.json()
    # process_telegram_event(data)
    return "ok"

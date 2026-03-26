import uvicorn
from core.webhook.server import webhook_app, callback_app
from core.config import settings
from fastfetchbot_shared.utils.logger import logger


if __name__ == "__main__":
    if settings.TELEGRAM_BOT_MODE == "webhook":
        logger.info(f"Running in webhook mode on port {settings.TELEGRAM_BOT_PORT}")
        uvicorn.run(webhook_app, host="0.0.0.0", port=settings.TELEGRAM_BOT_PORT)
    else:
        logger.info(f"Running in polling mode (HTTP server on port {settings.TELEGRAM_BOT_PORT} for callbacks)")
        uvicorn.run(callback_app, host="0.0.0.0", port=settings.TELEGRAM_BOT_PORT)

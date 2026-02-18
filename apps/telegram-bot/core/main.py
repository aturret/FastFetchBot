import uvicorn
from core.webhook.server import webhook_app, callback_app
from core.config import TELEGRAM_BOT_MODE
from fastfetchbot_shared.utils.logger import logger


if __name__ == "__main__":
    if TELEGRAM_BOT_MODE == "webhook":
        logger.info("Running in webhook mode on port 10451")
        uvicorn.run(webhook_app, host="0.0.0.0", port=10451)
    else:
        logger.info("Running in polling mode (HTTP server on port 10451 for callbacks)")
        uvicorn.run(callback_app, host="0.0.0.0", port=10451)

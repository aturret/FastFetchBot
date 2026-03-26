import os

from loguru import logger

from fastfetchbot_shared.config import settings

log_path = os.path.join(settings.LOG_FILE_PATH, "app.log")

logger.add(
    log_path,
    level=settings.LOG_LEVEL,
    rotation="1 week",
    retention="10 days",
    compression="zip",
)
logger.debug(f"Logger initialized with level: {settings.LOG_LEVEL}")
logger.debug(f"Logger initialized with log file path: {log_path}")

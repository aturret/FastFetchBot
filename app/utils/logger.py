import logging
import os

from loguru import logger

from app.config import LOG_LEVEL, LOG_FILE_PATH

log_path = os.path.join(LOG_FILE_PATH, "app.log")

logger.add(
    log_path,
    level=LOG_LEVEL,
    rotation="1 week",
    retention="10 days",
    compression="zip",
)
logger.debug(f"Logger initialized with level: {LOG_LEVEL}")
logger.debug(f"Logger initialized with log file path: {log_path}")

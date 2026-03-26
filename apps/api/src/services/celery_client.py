from celery import Celery
from src.config import settings

celery_app = Celery(
    "fastfetchbot_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

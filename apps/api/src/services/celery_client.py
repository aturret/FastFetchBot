from celery import Celery
from src.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "fastfetchbot_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

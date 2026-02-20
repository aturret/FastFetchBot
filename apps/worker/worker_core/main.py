from celery import Celery
from worker_core.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

app = Celery(
    "fastfetchbot_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=660,  # hard limit slightly above download timeout
    task_soft_time_limit=600,
    result_expires=3600,
)

# Auto-discover tasks
app.autodiscover_tasks(["worker_core"])

from celery import Celery
from ..config import settings

celery_app = Celery(
    "basin",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.relocate", "app.tasks.export"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

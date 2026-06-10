from celery import Celery
from src.core.config import settings

celery_app = Celery(
    "video_renderer_ecosystem",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Crucial to let workers execute concurrently and not get stuck on a single task type
    worker_prefetch_multiplier=1,
)

# Import tasks module to force registration
import src.infrastructure.queue.tasks  # noqa: F401

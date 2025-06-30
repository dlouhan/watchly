from celery import Celery
from app.config import settings

celery_app = Celery(
    "worker",
    broker=settings.redis_broker_url,
)
celery_app.conf.timezone = 'UTC'
celery_app.autodiscover_tasks(['app.tasks'])

from app import tasks  # <-- DŮLEŽITÉ, pro načtení scheduleru!
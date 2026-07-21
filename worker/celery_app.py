"""Celery: transcripcion, OCR, reportes programados y respaldos."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from backend.config import get_settings

settings = get_settings()

app = Celery("fruitflow", broker=settings.redis_url, backend=settings.redis_url)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.tz,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
)

app.conf.beat_schedule = {
    "resumen-diario": {
        "task": "worker.tasks.reportes.resumen_diario",
        "schedule": crontab(hour=20, minute=0),
    },
    "recordatorio-cajas": {
        "task": "worker.tasks.reportes.recordatorio_cajas",
        "schedule": crontab(hour=8, minute=0),
    },
    "expirar-borradores": {
        "task": "worker.tasks.mantenimiento.expirar_borradores",
        "schedule": crontab(minute=0),
    },
}

app.autodiscover_tasks(["worker.tasks"])

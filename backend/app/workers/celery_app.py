"""Aplicação Celery (FR-008)."""

from __future__ import annotations

from typing import Any

from celery import Celery
from celery.signals import setup_logging

from app.core.config import get_settings
from app.core.logging import configure_logging

HEARTBEAT_KEY = "climate:beat:last_heartbeat"
HEARTBEAT_INTERVAL_S = 30

_settings = get_settings()

celery_app = Celery(
    "climate",
    broker=_settings.redis_url,
    include=["app.workers.tasks.system"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "system-heartbeat": {
            "task": "system.heartbeat",
            "schedule": float(HEARTBEAT_INTERVAL_S),
        },
    },
)


@setup_logging.connect
def _configure_celery_logging(**_kwargs: Any) -> None:
    """Substitui o logging padrão do Celery pelo pipeline JSON."""
    configure_logging(_settings.log_level, service="worker")

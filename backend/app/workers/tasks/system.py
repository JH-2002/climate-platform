"""Tarefas de sistema: ping de vida e batimento (heartbeat) do agendador."""

from __future__ import annotations

from datetime import UTC, datetime

import redis
import structlog

from app.core.config import get_settings
from app.workers.celery_app import HEARTBEAT_KEY, celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="system.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="system.heartbeat")
def heartbeat() -> str:
    """Agendada pelo beat; prova que o caminho beat → broker → worker funciona."""
    now = datetime.now(UTC).isoformat()
    client = redis.Redis.from_url(get_settings().redis_url)
    try:
        client.set(HEARTBEAT_KEY, now, ex=600)
    finally:
        client.close()
    logger.debug("beat_heartbeat_recorded", at=now)
    return now

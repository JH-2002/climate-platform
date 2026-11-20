"""Aplicação Celery (FR-008)."""

from __future__ import annotations

from typing import Any

from celery import Celery
from celery.signals import beat_init, setup_logging

from app.core.config import get_settings
from app.core.logging import configure_logging

HEARTBEAT_KEY = "climate:beat:last_heartbeat"
HEARTBEAT_INTERVAL_S = 30
STATIONS_SYNC_INTERVAL_S = 24 * 3600
FORECAST_INTERVAL_S = 3600
GEOSAMPA_SYNC_INTERVAL_S = 24 * 3600
ARCHIVE_UPDATE_INTERVAL_S = 24 * 3600
# Carga inicial da reanálise: um ponto a cada 2 min (limite gratuito da fonte, NFR-082).
ARCHIVE_BACKFILL_INTERVAL_S = 120
REFERENCE_IMPORT_INTERVAL_S = 7 * 24 * 3600

_settings = get_settings()

celery_app = Celery(
    "climate",
    broker=_settings.redis_url,
    include=[
        "app.workers.tasks.system",
        "app.workers.tasks.ingestion",
        "app.workers.tasks.risk",
        "app.workers.tasks.analytics",
    ],
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
    # Agendas por intervalo só disparam após o primeiro intervalo; a coleta inicial é
    # enviada em _initial_ingestion (sinal beat_init).
    beat_schedule={
        "system-heartbeat": {
            "task": "system.heartbeat",
            "schedule": float(HEARTBEAT_INTERVAL_S),
        },
        "inmet-stations-sync": {
            "task": "ingestion.sync_inmet_stations",
            "schedule": float(STATIONS_SYNC_INTERVAL_S),
        },
        "open-meteo-forecast": {
            "task": "ingestion.open_meteo_forecast",
            "schedule": float(FORECAST_INTERVAL_S),
        },
        "geosampa-sync": {
            "task": "ingestion.sync_geosampa",
            "schedule": float(GEOSAMPA_SYNC_INTERVAL_S),
        },
        "open-meteo-archive": {
            "task": "ingestion.open_meteo_archive",
            "schedule": float(ARCHIVE_UPDATE_INTERVAL_S),
        },
        "open-meteo-archive-backfill": {
            "task": "ingestion.open_meteo_archive_backfill",
            "schedule": float(ARCHIVE_BACKFILL_INTERVAL_S),
        },
        "reference-import": {
            "task": "ingestion.import_reference",
            "schedule": float(REFERENCE_IMPORT_INTERVAL_S),
        },
    },
)


@setup_logging.connect
def _configure_celery_logging(**_kwargs: Any) -> None:
    """Substitui o logging padrão do Celery pelo pipeline JSON."""
    configure_logging(_settings.log_level, service="worker")


STARTUP_TASKS = (
    "ingestion.sync_inmet_stations",
    "ingestion.open_meteo_forecast",
    "ingestion.sync_geosampa",
    "ingestion.import_reference",
    "ingestion.open_meteo_archive_backfill",
    # A atualização diária também roda ao iniciar: reinícios frequentes do agendador
    # adiariam o ciclo de 24 h indefinidamente.
    "ingestion.open_meteo_archive",
)


@beat_init.connect
def _initial_ingestion(**_kwargs: Any) -> None:
    """Dispara uma coleta assim que o agendador inicia (sem esperar o primeiro intervalo)."""
    for task_name in STARTUP_TASKS:
        celery_app.send_task(task_name)

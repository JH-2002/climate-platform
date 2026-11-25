"""Tarefas Celery de ingestão. A agenda fica em `celery_app.beat_schedule`."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.ingestion.pipeline import RunOutcome
from app.ingestion.runner import run_forecast, run_station_sync
from app.workers.celery_app import celery_app


def _summary(outcome: RunOutcome) -> dict[str, Any]:
    return {
        "run_id": outcome.run_id,
        "status": outcome.status,
        "received": outcome.result.received,
        "inserted": outcome.result.inserted,
        "updated": outcome.result.updated,
        "rejected": outcome.result.rejected,
        "error": outcome.error,
    }


@celery_app.task(name="ingestion.sync_inmet_stations")
def sync_inmet_stations() -> dict[str, Any]:
    return _summary(asyncio.run(run_station_sync(get_settings())))


@celery_app.task(name="ingestion.open_meteo_forecast")
def open_meteo_forecast() -> dict[str, Any]:
    outcome = asyncio.run(run_forecast(get_settings()))
    # O risco estimado usa a previsão: recalcula logo após cada coleta (FR-064).
    celery_app.send_task("risk.compute_flood_risk")
    return _summary(outcome)

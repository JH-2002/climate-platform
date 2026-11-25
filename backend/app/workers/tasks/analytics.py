"""Tarefas Celery das séries de referência (spec 006)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.ingestion.pipeline import RunOutcome
from app.ingestion.runner import (
    run_archive_backfill,
    run_archive_update,
    run_forecast_archive,
    run_iag_import,
    run_risk_evaluation,
)
from app.workers.celery_app import celery_app


def _summary(outcome: RunOutcome | None) -> dict[str, Any]:
    if outcome is None:
        return {"status": "SKIPPED", "reason": "carga inicial completa"}
    return {
        "run_id": outcome.run_id,
        "status": outcome.status,
        "inserted": outcome.result.inserted,
        "updated": outcome.result.updated,
        "notes": outcome.result.notes,
        "error": outcome.error,
    }


@celery_app.task(name="ingestion.import_reference")
def import_reference() -> dict[str, Any]:
    return _summary(asyncio.run(run_iag_import(get_settings())))


@celery_app.task(name="ingestion.open_meteo_archive_backfill")
def open_meteo_archive_backfill() -> dict[str, Any]:
    return _summary(asyncio.run(run_archive_backfill(get_settings())))


@celery_app.task(name="ingestion.open_meteo_archive")
def open_meteo_archive() -> dict[str, Any]:
    return _summary(asyncio.run(run_archive_update(get_settings())))


@celery_app.task(name="ingestion.open_meteo_forecast_archive")
def open_meteo_forecast_archive() -> dict[str, Any]:
    """Arquivo de previsões (spec 015); em seguida recalcula a avaliação do motor."""
    outcome = asyncio.run(run_forecast_archive(get_settings()))
    celery_app.send_task("analytics.risk_evaluation")
    return _summary(outcome)


@celery_app.task(name="analytics.risk_evaluation", soft_time_limit=900)
def risk_evaluation() -> dict[str, Any]:
    summary = asyncio.run(run_risk_evaluation(get_settings()))
    return {
        "status": summary.status,
        "days": summary.days,
        "units": summary.units,
        "events": summary.events,
        "csi": summary.csi,
        "error": summary.error,
    }

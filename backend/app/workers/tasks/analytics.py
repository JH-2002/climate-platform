"""Tarefas Celery das séries de referência (spec 006)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.ingestion.pipeline import RunOutcome
from app.ingestion.runner import run_archive_backfill, run_archive_update, run_iag_import
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

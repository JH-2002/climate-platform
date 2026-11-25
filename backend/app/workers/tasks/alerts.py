"""Tarefas Celery dos alertas (spec 009). A agenda fica em `celery_app.beat_schedule`."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.ingestion.pipeline import RunOutcome
from app.ingestion.runner import (
    run_alert_evaluation,
    run_idap,
    run_inmet_warnings,
    run_subprefecture_sync,
)
from app.workers.celery_app import celery_app

EVALUATE_TASK = "alerts.evaluate"


def _summary(outcome: RunOutcome) -> dict[str, Any]:
    return {
        "run_id": outcome.run_id,
        "status": outcome.status,
        "received": outcome.result.received,
        "inserted": outcome.result.inserted,
        "error": outcome.error,
    }


@celery_app.task(name="alerts.fetch_idap")
def fetch_idap() -> dict[str, Any]:
    outcome = asyncio.run(run_idap(get_settings()))
    # Fonte parada é ela mesma um alerta do sistema (FR-144): reavalia após cada coleta.
    celery_app.send_task(EVALUATE_TASK)
    return _summary(outcome)


@celery_app.task(name="alerts.fetch_inmet")
def fetch_inmet() -> dict[str, Any]:
    outcome = asyncio.run(run_inmet_warnings(get_settings()))
    celery_app.send_task(EVALUATE_TASK)
    return _summary(outcome)


@celery_app.task(name="alerts.sync_subprefectures")
def sync_subprefectures() -> dict[str, Any]:
    return _summary(asyncio.run(run_subprefecture_sync(get_settings())))


@celery_app.task(name=EVALUATE_TASK)
def evaluate() -> dict[str, Any]:
    summary = asyncio.run(run_alert_evaluation(get_settings()))
    return {
        "opened": summary.opened,
        "updated": summary.updated,
        "closed": summary.closed,
        "open_total": summary.open_total,
    }

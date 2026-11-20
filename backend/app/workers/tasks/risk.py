"""Tarefas Celery do risco de alagamento (spec 005)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.ingestion.runner import run_flood_risk, run_geosampa_sync
from app.workers.celery_app import celery_app

COMPUTE_TASK = "risk.compute_flood_risk"


@celery_app.task(name="ingestion.sync_geosampa")
def sync_geosampa() -> dict[str, Any]:
    outcomes = asyncio.run(run_geosampa_sync(get_settings()))
    # Novas camadas mudam a suscetibilidade: recalcula o risco em seguida.
    celery_app.send_task(COMPUTE_TASK)
    return {
        code: {"run_id": o.run_id, "status": o.status, "error": o.error} for code, o in outcomes
    }


@celery_app.task(name=COMPUTE_TASK)
def compute_flood_risk() -> dict[str, Any]:
    summary = asyncio.run(run_flood_risk(get_settings()))
    return {
        "run_id": summary.run_id,
        "status": summary.status,
        "sectors": summary.sector_count,
        "counts": dict(summary.counts),
        "error": summary.error,
    }

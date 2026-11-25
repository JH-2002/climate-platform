"""Tarefas Celery da geointeligência (spec 008)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.ingestion.runner import run_geo_refresh
from app.workers.celery_app import celery_app

GEO_REFRESH_TASK = "geo.refresh"


@celery_app.task(name=GEO_REFRESH_TASK)
def geo_refresh() -> dict[str, Any]:
    """Hidrografia (30 dias), DEM (uma vez) e terreno; cada etapa se pula quando em dia."""
    report = asyncio.run(run_geo_refresh(get_settings()))
    return {
        "runs": [
            {"source": code, "status": o.status, "notes": o.result.notes, "error": o.error}
            for code, o in report.outcomes
        ],
        "skipped": report.skipped,
        "terrain": None if report.terrain is None else report.terrain.__dict__,
    }

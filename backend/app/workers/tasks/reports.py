"""Tarefas Celery da central de relatórios (spec 010)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.ingestion.runner import run_report_generation, run_report_housekeeping
from app.workers.celery_app import celery_app


@celery_app.task(name="reports.generate")
def generate(request_id: str) -> dict[str, Any]:
    return {"status": asyncio.run(run_report_generation(get_settings(), request_id))}


@celery_app.task(name="reports.housekeeping")
def housekeeping() -> dict[str, Any]:
    expired, stuck = asyncio.run(run_report_housekeeping(get_settings()))
    return {"expired_files": expired, "stuck_failed": stuck}

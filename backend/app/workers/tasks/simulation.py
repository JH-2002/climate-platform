"""Tarefas Celery do laboratório de simulação (spec 007)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.services.simulation import purge_old_runs
from app.workers.celery_app import celery_app

PURGE_TASK = "simulation.purge_old_runs"


async def _purge() -> int:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            removed = await purge_old_runs(session, datetime.now(UTC))
            await session.commit()
            return removed
    finally:
        await engine.dispose()


@celery_app.task(name=PURGE_TASK)
def purge_simulations() -> dict[str, Any]:
    """NFR-102: retenção de 30 dias e no máximo 500 execuções."""
    return {"removed": asyncio.run(_purge())}

"""Liga os jobs à infraestrutura real (banco e HTTP). Usado pelas tarefas Celery."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.ingestion.jobs import Fetcher, make_forecast_job, make_station_sync_job
from app.ingestion.pipeline import RunOutcome, run_ingestion
from app.integrations.http import fetch

STATIONS_SOURCE = "inmet-stations"
FORECAST_SOURCE = "open-meteo-forecast"


@asynccontextmanager
async def _session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # NullPool: cada tarefa Celery roda num event loop próprio e não deve reaproveitar conexões.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


def make_http_fetcher(client: httpx.AsyncClient) -> Fetcher:
    async def fetcher(url: str, params: dict[str, str] | None) -> Any:
        result = await fetch(client, url, params=params)
        if result.is_empty:
            return None
        return json.loads(result.body)

    return fetcher


async def run_station_sync(settings: Settings) -> RunOutcome:
    async with (
        _session_factory(settings) as sessions,
        httpx.AsyncClient(timeout=settings.http_timeout_s) as client,
    ):
        job = make_station_sync_job(make_http_fetcher(client), settings.region)
        return await run_ingestion(sessions, STATIONS_SOURCE, job)


async def run_forecast(settings: Settings) -> RunOutcome:
    async with (
        _session_factory(settings) as sessions,
        httpx.AsyncClient(timeout=settings.http_timeout_s) as client,
    ):
        job = make_forecast_job(make_http_fetcher(client), settings.forecast_point_list)
        return await run_ingestion(sessions, FORECAST_SOURCE, job)

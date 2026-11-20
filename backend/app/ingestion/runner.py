"""Liga os jobs à infraestrutura real (banco e HTTP). Usado pelas tarefas Celery."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.ingestion.archive_jobs import (
    make_archive_backfill_job,
    make_archive_update_job,
    pending_points,
)
from app.ingestion.geosampa_jobs import (
    make_flood_extent_sync_job,
    make_occurrence_sync_job,
    make_sector_sync_job,
)
from app.ingestion.jobs import Fetcher, make_forecast_job, make_station_sync_job
from app.ingestion.pipeline import RunOutcome, run_ingestion
from app.ingestion.reference_import import make_iag_import_job
from app.integrations.http import fetch
from app.models.tables import data_sources
from app.services.risk import RiskRunSummary, compute_flood_risk

STATIONS_SOURCE = "inmet-stations"
FORECAST_SOURCE = "open-meteo-forecast"
GEOSAMPA_SECTORS_SOURCE = "geosampa-risk-sectors"
GEOSAMPA_EXTENT_SOURCE = "geosampa-flood-extent"
GEOSAMPA_OCCURRENCES_SOURCE = "geosampa-flood-occurrences"
ARCHIVE_SOURCE = "open-meteo-archive"
IAG_SOURCE = "iag-usp-rain-monthly"
# 35 anos diários de um ponto levam ~11 s na fonte (SOURCES.md §12).
ARCHIVE_TIMEOUT_S = 90.0
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
# Camadas do GeoSampa chegam a 1,6 MB; o servidor responde devagar em horários de pico.
GEOSAMPA_TIMEOUT_S = 60.0


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


async def run_geosampa_sync(settings: Settings) -> list[tuple[str, RunOutcome]]:
    """Setores, manchas e ocorrências: uma execução por fonte; a falha de uma não para as outras."""
    timeout = max(settings.http_timeout_s, GEOSAMPA_TIMEOUT_S)
    async with (
        _session_factory(settings) as sessions,
        httpx.AsyncClient(timeout=timeout) as client,
    ):
        fetcher = make_http_fetcher(client)
        url = settings.geosampa_wfs_url
        jobs = [
            (GEOSAMPA_SECTORS_SOURCE, make_sector_sync_job(fetcher, url)),
            (GEOSAMPA_EXTENT_SOURCE, make_flood_extent_sync_job(fetcher, url)),
            (GEOSAMPA_OCCURRENCES_SOURCE, make_occurrence_sync_job(fetcher, url)),
        ]
        return [(code, await run_ingestion(sessions, code, job)) for code, job in jobs]


async def run_flood_risk(settings: Settings) -> RiskRunSummary:
    """Motor de risco v0 (spec 005, FR-064) sobre os dados já coletados."""
    async with _session_factory(settings) as sessions, sessions() as session:
        return await compute_flood_risk(session, datetime.now(UTC))


def local_yesterday(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(LOCAL_TZ).date() - timedelta(days=1)


async def run_iag_import(settings: Settings) -> RunOutcome:
    async with _session_factory(settings) as sessions:
        return await run_ingestion(sessions, IAG_SOURCE, make_iag_import_job())


async def run_archive_backfill(settings: Settings) -> RunOutcome | None:
    """Carga inicial de um ponto. Sem pontos pendentes, não registra execução."""
    points = settings.forecast_point_list
    async with _session_factory(settings) as sessions:
        async with sessions() as session:
            source_id = (
                await session.execute(
                    select(data_sources.c.id).where(data_sources.c.code == ARCHIVE_SOURCE)
                )
            ).scalar_one()
            if not await pending_points(session, source_id, points):
                return None
        async with httpx.AsyncClient(timeout=ARCHIVE_TIMEOUT_S) as client:
            job = make_archive_backfill_job(make_http_fetcher(client), points, local_yesterday())
            return await run_ingestion(sessions, ARCHIVE_SOURCE, job)


async def run_archive_update(settings: Settings) -> RunOutcome:
    async with (
        _session_factory(settings) as sessions,
        httpx.AsyncClient(timeout=ARCHIVE_TIMEOUT_S) as client,
    ):
        job = make_archive_update_job(
            make_http_fetcher(client), settings.forecast_point_list, local_yesterday()
        )
        return await run_ingestion(sessions, ARCHIVE_SOURCE, job)

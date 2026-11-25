"""Liga os jobs à infraestrutura real (banco e HTTP). Usado pelas tarefas Celery."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.ingestion.alert_jobs import (
    BytesFetcher,
    make_idap_job,
    make_inmet_job,
    make_subprefecture_sync_job,
)
from app.ingestion.archive_jobs import (
    make_archive_backfill_job,
    make_archive_update_job,
    pending_points,
)
from app.ingestion.geo_jobs import (
    Download,
    make_basin_sync_job,
    make_dem_job,
    make_drainage_sync_job,
    make_reservoir_sync_job,
)
from app.ingestion.geosampa_jobs import (
    make_flood_extent_sync_job,
    make_occurrence_sync_job,
    make_sector_sync_job,
)
from app.ingestion.jobs import Fetcher, make_forecast_job, make_station_sync_job
from app.ingestion.pipeline import RunOutcome, run_ingestion
from app.ingestion.reference_import import make_iag_import_job
from app.integrations.http import USER_AGENT, fetch
from app.models.tables import data_sources, hydro_risk_sectors, ingestion_runs, sector_terrain
from app.services.alerts import EvaluationSummary, evaluate_system_alerts, thresholds_from
from app.services.geo import DEM_CLIP_CODE, TerrainSummary, compute_terrain, dem_status
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
# Drenagem: ~28 MB numa resposta (SOURCES.md §13).
HYDRO_TIMEOUT_S = 180.0
HYDRO_INTERVAL = timedelta(days=30)
TERRAIN_MAX_AGE = timedelta(hours=20)
DEM_SOURCE = "copernicus-dem"
IDAP_SOURCE = "idap-alerts"
INMET_WARNINGS_SOURCE = "inmet-warnings"
SUBPREFECTURES_SOURCE = "geosampa-subprefectures"
# Feed da IDAP: ~16 MB (SOURCES.md §15); limite de 60 MB na leitura.
IDAP_TIMEOUT_S = 120.0
IDAP_MAX_BYTES = 60 * 1024 * 1024
HYDRO_SOURCES = (
    ("geosampa-basins", make_basin_sync_job),
    ("geosampa-drainage", make_drainage_sync_job),
    ("geosampa-reservoirs", make_reservoir_sync_job),
)


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


# --- geointeligência (spec 008) ---------------------------------------------------------------


def make_http_downloader(client: httpx.AsyncClient) -> Any:
    """Grava a resposta em streaming num arquivo temporário e só então troca pelo definitivo."""

    async def download(url: str, dest: Path) -> Download:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        written = 0
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            expected = response.headers.get("content-length")
            with tmp.open("wb") as fh:
                async for chunk in response.aiter_bytes(1 << 20):
                    fh.write(chunk)
                    written += len(chunk)
            etag = response.headers.get("etag")
        if expected is not None and int(expected) != written:
            tmp.unlink(missing_ok=True)
            raise ValueError(f"download incompleto: {written} de {expected} bytes")
        tmp.replace(dest)
        return Download(etag=etag.strip('"') if etag else None, bytes=written)

    return download


async def _last_success(session: AsyncSession, code: str) -> datetime | None:
    last: datetime | None = (
        await session.execute(
            select(func.max(ingestion_runs.c.finished_at))
            .join(data_sources, data_sources.c.id == ingestion_runs.c.source_id)
            .where(data_sources.c.code == code, ingestion_runs.c.status == "SUCCESS")
        )
    ).scalar_one_or_none()
    return last


async def _terrain_due(session: AsyncSession, now: datetime) -> bool:
    """Falta terreno para algum setor ativo, ou o cálculo mais antigo venceu."""
    sectors = (
        await session.execute(
            select(func.count())
            .select_from(hydro_risk_sectors)
            .where(hydro_risk_sectors.c.active.is_(True))
        )
    ).scalar_one()
    if not sectors:
        return False
    computed, oldest = (
        await session.execute(select(func.count(), func.min(sector_terrain.c.computed_at)))
    ).one()
    return bool(computed < sectors or oldest is None or now - oldest > TERRAIN_MAX_AGE)


@dataclass
class GeoRefresh:
    outcomes: list[tuple[str, RunOutcome]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    terrain: TerrainSummary | None = None


async def run_geo_refresh(settings: Settings, now: datetime | None = None) -> GeoRefresh:
    """Hidrografia (a cada 30 dias), DEM (uma vez) e terreno (quando algo mudou ou venceu)."""
    now = now or datetime.now(UTC)
    report = GeoRefresh()
    changed = False
    async with _session_factory(settings) as sessions:
        async with httpx.AsyncClient(timeout=HYDRO_TIMEOUT_S) as client:
            fetcher = make_http_fetcher(client)
            for code, factory in HYDRO_SOURCES:
                async with sessions() as session:
                    last = await _last_success(session, code)
                if last is not None and now - last < HYDRO_INTERVAL:
                    report.skipped.append(code)
                    continue
                outcome = await run_ingestion(
                    sessions, code, factory(fetcher, settings.geosampa_wfs_url)
                )
                report.outcomes.append((code, outcome))
                changed = changed or outcome.status == "SUCCESS"
            async with sessions() as session:
                dem_ready = (await dem_status(session, settings)).available
            if dem_ready:
                report.skipped.append(DEM_SOURCE)
            else:
                region = settings.region
                job = make_dem_job(
                    make_http_downloader(client),
                    settings.copernicus_dem_url,
                    settings.dem_dir,
                    (region.lon_min, region.lat_min, region.lon_max, region.lat_max),
                    DEM_CLIP_CODE,
                )
                outcome = await run_ingestion(sessions, DEM_SOURCE, job)
                report.outcomes.append((DEM_SOURCE, outcome))
                changed = changed or outcome.status == "SUCCESS"
        async with sessions() as session:
            if changed or await _terrain_due(session, now):
                report.terrain = await compute_terrain(session, settings, now)
    return report


# --- alertas (spec 009) -----------------------------------------------------------------------


def make_bytes_fetcher(client: httpx.AsyncClient, max_bytes: int = IDAP_MAX_BYTES) -> BytesFetcher:
    """Corpo bruto da resposta, com teto de tamanho lido em fluxo (o XML vem de fora)."""

    async def fetch_bytes(url: str) -> bytes | None:
        chunks: list[bytes] = []
        size = 0
        async with client.stream("GET", url, headers={"User-Agent": USER_AGENT}) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(1 << 16):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"resposta acima de {max_bytes // (1024 * 1024)} MB")
                chunks.append(chunk)
        return b"".join(chunks) or None

    return fetch_bytes


async def run_idap(settings: Settings) -> RunOutcome:
    async with (
        _session_factory(settings) as sessions,
        httpx.AsyncClient(timeout=IDAP_TIMEOUT_S, follow_redirects=True) as client,
    ):
        job = make_idap_job(
            make_bytes_fetcher(client),
            settings.idap_feed_url,
            settings.region,
            settings.region_ibge_code,
        )
        return await run_ingestion(sessions, IDAP_SOURCE, job)


async def run_inmet_warnings(settings: Settings) -> RunOutcome:
    async with (
        _session_factory(settings) as sessions,
        httpx.AsyncClient(timeout=settings.http_timeout_s, follow_redirects=True) as client,
    ):
        job = make_inmet_job(
            make_bytes_fetcher(client, 5 * 1024 * 1024),
            settings.inmet_warnings_url,
            settings.region,
            settings.region_ibge_code,
        )
        return await run_ingestion(sessions, INMET_WARNINGS_SOURCE, job)


async def run_subprefecture_sync(settings: Settings) -> RunOutcome:
    timeout = max(settings.http_timeout_s, GEOSAMPA_TIMEOUT_S)
    async with (
        _session_factory(settings) as sessions,
        httpx.AsyncClient(timeout=timeout) as client,
    ):
        job = make_subprefecture_sync_job(make_http_fetcher(client), settings.geosampa_wfs_url)
        return await run_ingestion(sessions, SUBPREFECTURES_SOURCE, job)


async def run_alert_evaluation(settings: Settings) -> EvaluationSummary:
    async with _session_factory(settings) as sessions, sessions() as session:
        return await evaluate_system_alerts(session, datetime.now(UTC), thresholds_from(settings))

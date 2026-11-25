"""T015/T016 — pipeline e jobs contra PostgreSQL/PostGIS real, com respostas reais gravadas.

Cobre FR-021, FR-023, FR-024, FR-025, FR-029 e AC-020, AC-023.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.geo import BoundingBox
from app.ingestion.jobs import make_forecast_job, make_station_sync_job
from app.ingestion.pipeline import JobResult, run_ingestion
from app.models.tables import (
    data_sources,
    ingestion_runs,
    raw_payloads,
    weather_forecasts,
    weather_stations,
)
from app.tests.fixtures import INMET_STATIONS_SP, OPEN_METEO_SP, load

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

SAO_PAULO = BoundingBox.parse("-46.83,-24.01,-46.36,-23.35")


@asynccontextmanager
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


def run[T](fn: Callable[[async_sessionmaker[AsyncSession]], Awaitable[T]]) -> T:
    async def go() -> T:
        async with sessions() as factory:
            return await fn(factory)

    return asyncio.run(go())


def fixed(payload: Any) -> Callable[[str, dict[str, str] | None], Awaitable[Any]]:
    async def fetcher(_url: str, _params: dict[str, str] | None) -> Any:
        return copy.deepcopy(payload)

    return fetcher


async def count(factory: async_sessionmaker[AsyncSession], table: Any, *where: Any) -> int:
    async with factory() as s:
        stmt = select(func.count()).select_from(table)
        if where:
            stmt = stmt.where(*where)
        return int((await s.execute(stmt)).scalar_one())


def test_station_sync_is_idempotent_and_records_run() -> None:
    job = make_station_sync_job(fixed(load(INMET_STATIONS_SP)), SAO_PAULO)

    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        first = await run_ingestion(f, "inmet-stations", job)
        assert first.status == "SUCCESS"
        assert (first.result.inserted, first.result.updated) == (2, 0)
        second = await run_ingestion(f, "inmet-stations", job)
        assert (second.result.inserted, second.result.updated) == (0, 2)

        assert await count(f, weather_stations) == 2
        assert await count(f, ingestion_runs, ingestion_runs.c.status == "SUCCESS") == 2
        assert await count(f, raw_payloads) == 1  # mesmo payload não é duplicado (FR-024)
        async with f() as s:
            source = (
                await s.execute(select(data_sources).where(data_sources.c.code == "inmet-stations"))
            ).one()
        assert source.last_status == "SUCCESS"
        assert source.last_success_at is not None

    run(scenario)


def test_station_missing_from_list_becomes_inactive() -> None:
    payload = load(INMET_STATIONS_SP)
    without_interlagos = [s for s in payload if s["CD_ESTACAO"] != "A771"]

    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        await run_ingestion(f, "inmet-stations", make_station_sync_job(fixed(payload), SAO_PAULO))
        await run_ingestion(
            f, "inmet-stations", make_station_sync_job(fixed(without_interlagos), SAO_PAULO)
        )
        async with f() as s:
            query = select(weather_stations.c.external_code, weather_stations.c.status)
            rows = dict((await s.execute(query)).tuples().all())
        assert rows == {"A701": "OPERATIONAL", "A771": "INACTIVE"}

    run(scenario)


def test_forecast_ingestion_is_idempotent() -> None:
    job = make_forecast_job(fixed(load(OPEN_METEO_SP)), [(-23.55, -46.63)])

    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        first = await run_ingestion(f, "open-meteo-forecast", job)
        assert first.status == "SUCCESS"
        assert first.result.inserted == 168 * 4 + 7 * 4
        second = await run_ingestion(f, "open-meteo-forecast", job)
        assert (second.result.inserted, second.result.updated) == (0, 700)
        assert await count(f, weather_forecasts) == 700
        assert (
            await count(f, weather_forecasts, weather_forecasts.c.kind != "FORECAST")
        ) == 0  # previsão nunca vira observação (Constituição §7)

    run(scenario)


def test_failure_is_recorded_and_circuit_opens_after_five() -> None:
    async def broken(_ctx: Any) -> JobResult:
        raise ConnectionError("postgresql://u:segredo@host recusou")

    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        for _ in range(5):
            outcome = await run_ingestion(f, "open-meteo-forecast", broken)
            assert outcome.status == "FAILED"
            assert "segredo" not in (outcome.error or "")
        sixth = await run_ingestion(f, "open-meteo-forecast", broken)
        assert sixth.status == "FAILED"
        assert (sixth.error or "").startswith("circuit_open")
        assert await count(f, ingestion_runs, ingestion_runs.c.status == "FAILED") == 6

    run(scenario)

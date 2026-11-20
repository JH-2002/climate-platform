"""T074 — importação do IAG/USP e reanálise com retomada (AC-080, AC-081, NFR-082)."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.archive_jobs import make_archive_backfill_job, make_archive_update_job
from app.ingestion.pipeline import run_ingestion
from app.ingestion.reference_import import make_iag_import_job
from app.models.tables import (
    backfill_progress,
    climate_daily,
    published_normals,
    rain_monthly_observed,
    raw_payloads,
)
from app.tests.fixtures import OPEN_METEO_ARCHIVE_SP, load
from app.tests.integration.test_flood_sync import run, scalar

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

POINTS = [(-23.57, -46.62), (-23.69, -46.62)]
YESTERDAY = date(2026, 11, 18)


def archive_fetcher(calls: list[dict[str, str]]) -> Any:
    async def fetcher(_url: str, params: dict[str, str] | None) -> Any:
        calls.append(dict(params or {}))
        return copy.deepcopy(load(OPEN_METEO_ARCHIVE_SP))

    return fetcher


def test_ac080_iag_import_is_idempotent() -> None:
    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        first = await run_ingestion(f, "iag-usp-rain-monthly", make_iag_import_job())
        assert first.status == "SUCCESS"
        assert (first.result.inserted, first.result.updated) == (93 * 12, 0)
        second = await run_ingestion(f, "iag-usp-rain-monthly", make_iag_import_job())
        assert (second.result.inserted, second.result.updated) == (0, 93 * 12)
        m = rain_monthly_observed
        assert await scalar(f, select(func.count()).select_from(m)) == 1116
        assert await scalar(f, select(func.sum(m.c.value_mm)).where(m.c.year == 1933)) == (
            pytest.approx(849.8)
        )
        assert await scalar(f, select(func.min(m.c.kind))) == "OBSERVED"
        n = published_normals
        annual = await scalar(
            f, select(n.c.value_mm).where(n.c.period == "1991-2020", n.c.month == 0)
        )
        assert annual == pytest.approx(1559.2)
        assert await scalar(f, select(func.count()).select_from(raw_payloads)) == 1

    run(scenario)


def test_ac081_backfill_one_point_per_run_then_stops() -> None:
    calls: list[dict[str, str]] = []

    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        job = make_archive_backfill_job(archive_fetcher(calls), POINTS, YESTERDAY)
        first = await run_ingestion(f, "open-meteo-archive", job)
        assert first.status == "SUCCESS" and first.result.inserted == 92 * 4
        assert calls[0]["start_date"] == "1991-01-01" and calls[0]["end_date"] == "2026-11-18"
        assert calls[0]["latitude"] == "-23.5700"
        second = await run_ingestion(f, "open-meteo-archive", job)
        assert second.result.inserted == 92 * 4 and calls[1]["latitude"] == "-23.6900"
        third = await run_ingestion(f, "open-meteo-archive", job)
        assert third.result.notes == ["carga inicial completa"] and len(calls) == 2
        c = climate_daily
        assert await scalar(f, select(func.count(func.distinct(c.c.point_key)))) == 2
        assert await scalar(f, select(func.min(c.c.kind))) == "MODELED"
        cell = await scalar(f, select(func.min(c.c.cell_key)))
        assert cell == "-23.5852,-46.6596"  # célula devolvida pela fonte, não o ponto pedido
        done = await scalar(f, select(func.count()).where(backfill_progress.c.completed.is_(True)))
        assert done == 2

    run(scenario)


def test_update_refreshes_last_days_without_duplicates() -> None:
    calls: list[dict[str, str]] = []

    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        fetcher = archive_fetcher(calls)
        await run_ingestion(
            f, "open-meteo-archive", make_archive_backfill_job(fetcher, POINTS[:1], YESTERDAY)
        )
        update = await run_ingestion(
            f, "open-meteo-archive", make_archive_update_job(fetcher, POINTS, YESTERDAY)
        )
        assert update.status == "SUCCESS"
        assert calls[-1]["start_date"] == "2026-11-09" and calls[-1]["end_date"] == "2026-11-18"
        assert "pontos aguardando a carga inicial: 1" in update.result.notes
        assert (update.result.inserted, update.result.updated) == (0, 92 * 4)
        assert await scalar(f, select(func.count()).select_from(climate_daily)) == 92 * 4

    run(scenario)

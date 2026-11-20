"""T053 — sincronização das camadas do GeoSampa com recortes reais (FR-060, AC-060)."""

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
from app.ingestion.geosampa_jobs import (
    make_flood_extent_sync_job,
    make_occurrence_sync_job,
    make_sector_sync_job,
)
from app.ingestion.pipeline import run_ingestion
from app.models.tables import (
    data_sources,
    flood_extent_areas,
    flood_occurrences,
    hydro_risk_sectors,
    raw_payloads,
)
from app.tests.fixtures import (
    GEOSAMPA_FLOOD_EXTENT,
    GEOSAMPA_OCC_ALAGAMENTO,
    GEOSAMPA_OCC_INUNDACAO,
    GEOSAMPA_SECTORS,
    load,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

URL = "http://wfs.test/geoserver/geoportal/wfs"
LAYERS = {
    "geoportal:risco_hidrologico": GEOSAMPA_SECTORS,
    "geoportal:area_inundavel": GEOSAMPA_FLOOD_EXTENT,
    "geoportal:risco_ocorrencia_alagamento": GEOSAMPA_OCC_ALAGAMENTO,
    "geoportal:risco_ocorrencia_inundacao": GEOSAMPA_OCC_INUNDACAO,
}

Fetcher = Callable[[str, dict[str, str] | None], Awaitable[Any]]


def geosampa_fetcher(overrides: dict[str, Any] | None = None, stamp: str = "t1") -> Fetcher:
    """Responde por camada, como o WFS real. `stamp` simula o carimbo que muda a cada pedido."""

    async def fetcher(_url: str, params: dict[str, str] | None) -> Any:
        layer = (params or {})["typeNames"]
        if overrides and layer in overrides:
            return copy.deepcopy(overrides[layer])
        payload = load(LAYERS[layer])
        payload["timeStamp"] = stamp
        return payload

    return fetcher


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


async def scalar(f: async_sessionmaker[AsyncSession], query: Any) -> Any:
    async with f() as s:
        return (await s.execute(query)).scalar_one()


async def sync_all(f: async_sessionmaker[AsyncSession], fetcher: Fetcher) -> list[Any]:
    return [
        await run_ingestion(f, "geosampa-risk-sectors", make_sector_sync_job(fetcher, URL)),
        await run_ingestion(f, "geosampa-flood-extent", make_flood_extent_sync_job(fetcher, URL)),
        await run_ingestion(
            f, "geosampa-flood-occurrences", make_occurrence_sync_job(fetcher, URL)
        ),
    ]


def test_ac060_sync_is_idempotent() -> None:
    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        first = await sync_all(f, geosampa_fetcher(stamp="t1"))
        assert [o.status for o in first] == ["SUCCESS"] * 3
        assert [o.result.inserted for o in first] == [6, 2, 16]
        second = await sync_all(f, geosampa_fetcher(stamp="t2"))
        assert [(o.result.inserted, o.result.updated) for o in second] == [(0, 6), (0, 2), (0, 16)]
        assert await scalar(f, select(func.count()).select_from(hydro_risk_sectors)) == 6
        assert await scalar(f, select(func.count()).select_from(flood_extent_areas)) == 2
        assert await scalar(f, select(func.count()).select_from(flood_occurrences)) == 16
        # o carimbo de hora do GeoServer não gera um novo payload bruto (FR-024)
        assert await scalar(f, select(func.count()).select_from(raw_payloads)) == 4

    run(scenario)


def test_geometries_are_valid_multipolygons() -> None:
    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        await sync_all(f, geosampa_fetcher())
        s = hydro_risk_sectors
        types = await scalar(
            f, select(func.array_agg(func.distinct(func.ST_GeometryType(s.c.geom))))
        )
        assert types == ["ST_MultiPolygon"]
        assert await scalar(f, select(func.bool_and(func.ST_IsValid(s.c.geom)))) is True
        assert await scalar(f, select(func.min(func.ST_SRID(s.c.geom)))) == 4326
        grade = await scalar(f, select(s.c.grade).where(s.c.source_code == "HMP-01-03"))
        assert grade == 3

    run(scenario)


def test_sector_missing_from_source_is_deactivated_not_deleted() -> None:
    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        await sync_all(f, geosampa_fetcher())
        payload = load(GEOSAMPA_SECTORS)
        payload["features"] = [
            feat
            for feat in payload["features"]
            if not feat["properties"]["sg_setor_risco_hidrologico"].startswith("HAF-06-02")
        ]
        fetcher = geosampa_fetcher({"geoportal:risco_hidrologico": payload})
        outcome = await run_ingestion(
            f, "geosampa-risk-sectors", make_sector_sync_job(fetcher, URL)
        )
        assert outcome.status == "SUCCESS"
        s = hydro_risk_sectors
        active = await scalar(f, select(s.c.active).where(s.c.source_code == "HAF-06-02"))
        assert active is False
        assert await scalar(f, select(func.count()).select_from(s)) == 6

    run(scenario)


def test_empty_layer_fails_and_keeps_previous_data() -> None:
    async def scenario(f: async_sessionmaker[AsyncSession]) -> None:
        await sync_all(f, geosampa_fetcher())
        empty = {"type": "FeatureCollection", "features": []}
        fetcher = geosampa_fetcher({"geoportal:risco_hidrologico": empty})
        outcome = await run_ingestion(
            f, "geosampa-risk-sectors", make_sector_sync_job(fetcher, URL)
        )
        assert outcome.status == "FAILED"
        assert "dados anteriores mantidos" in (outcome.error or "")
        s = hydro_risk_sectors
        assert await scalar(f, select(func.count()).where(s.c.active.is_(True))) == 6
        status = await scalar(
            f,
            select(data_sources.c.last_status).where(
                data_sources.c.code == "geosampa-risk-sectors"
            ),
        )
        assert status == "FAILED"

    run(scenario)

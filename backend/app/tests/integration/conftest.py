"""Banco limpo para cada teste de integração (dados de teste, nunca de produção)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest

if not os.environ.get("RUN_INTEGRATION"):
    pytest.skip("defina RUN_INTEGRATION=1 para rodar a integração", allow_module_level=True)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_TABLES = (
    "basin_terrain, sector_terrain, dem_assets, detention_reservoirs, drainage_segments, basins, "
    "simulation_results, simulation_runs, "
    "climate_daily, rain_monthly_observed, published_normals, backfill_progress, "
    "risk_assessments, risk_runs, flood_occurrences, flood_extent_areas, hydro_risk_sectors, "
    "weather_forecasts, weather_observations, raw_payloads, ingestion_runs, weather_stations"
)


async def _reset() -> None:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
        await conn.execute(
            text(
                "UPDATE data_sources SET last_attempt_at = NULL, last_success_at = NULL,"
                " last_status = NULL, last_error = NULL, enabled = true"
            )
        )
    await engine.dispose()


@pytest.fixture
def clean_db() -> Iterator[None]:
    asyncio.run(_reset())
    yield

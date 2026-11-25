"""T042 — rotas do mapa com respostas reais gravadas (AC-050, AC-054)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.deps import get_clock
from app.core.config import get_settings
from app.core.geo import BoundingBox
from app.ingestion.jobs import make_forecast_job, make_station_sync_job
from app.ingestion.pipeline import run_ingestion
from app.main import create_app
from app.tests.fixtures import INMET_STATIONS_SP, OPEN_METEO_SP, load

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

FIXED_NOW = datetime(2026, 11, 19, 15, 20, tzinfo=UTC)


def _seed() -> None:
    async def stations(_url: str, _params: dict[str, str] | None) -> object:
        return load(INMET_STATIONS_SP)

    async def forecast(_url: str, _params: dict[str, str] | None) -> object:
        return load(OPEN_METEO_SP)

    async def go() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        region = BoundingBox.parse("-46.83,-24.01,-46.36,-23.35")
        await run_ingestion(factory, "inmet-stations", make_station_sync_job(stations, region))
        await run_ingestion(
            factory, "open-meteo-forecast", make_forecast_job(forecast, [(-23.55, -46.63)])
        )
        await engine.dispose()

    asyncio.run(go())


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW
    with TestClient(app) as test_client:
        yield test_client


def test_region_is_closed_polygon(client: TestClient) -> None:
    body = client.get("/api/v1/map/region").json()
    assert body["type"] == "Feature"
    assert body["geometry"]["type"] == "Polygon"
    ring = body["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    assert body["properties"]["kind"] == "REGION"


def test_stations_layer(client: TestClient) -> None:
    _seed()
    body = client.get("/api/v1/map/layers/stations").json()
    assert body["type"] == "FeatureCollection"
    by_code = {f["properties"]["code"]: f for f in body["features"]}
    assert set(by_code) == {"A701", "A771"}
    lon, lat = by_code["A701"]["geometry"]["coordinates"]
    assert (round(lon, 4), round(lat, 4)) == (-46.6201, -23.4963)
    assert by_code["A701"]["properties"]["status"] == "OPERATIONAL"


def test_forecast_points_layer(client: TestClient) -> None:
    _seed()
    body = client.get("/api/v1/map/layers/forecast-points").json()
    assert len(body["features"]) == 1
    props = body["features"][0]["properties"]
    assert props["kind"] == "FORECAST"
    assert props["air_temperature_now"] == pytest.approx(30.2)
    # 24 h a partir de 15:00Z na resposta gravada
    assert props["precipitation_24h_complete"] is True
    assert props["precipitation_24h"] == pytest.approx(1.0)
    assert "CC BY 4.0" in body["attribution"]


def test_invalid_bbox(client: TestClient) -> None:
    assert client.get("/api/v1/map/layers/stations?bbox=x").status_code == 422

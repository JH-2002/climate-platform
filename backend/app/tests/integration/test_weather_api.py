"""T032 — /weather/forecast com a previsão real gravada e relógio fixo (AC-040, AC-041)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.weather import get_clock
from app.core.config import get_settings
from app.ingestion.jobs import make_forecast_job
from app.ingestion.pipeline import run_ingestion
from app.main import create_app
from app.tests.fixtures import OPEN_METEO_SP, load

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

# A resposta gravada cobre 2026-11-19T00:00Z a 2026-11-25T23:00Z (timezone=UTC na gravação).
FIXED_NOW = datetime(2026, 11, 19, 15, 20, tzinfo=UTC)
PAULISTA = (-23.5614, -46.6559)


def _seed_forecast() -> None:
    async def fetcher(_url: str, _params: dict[str, str] | None) -> object:
        return load(OPEN_METEO_SP)

    async def go() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        job = make_forecast_job(fetcher, [(-23.55, -46.63)])
        await run_ingestion(factory, "open-meteo-forecast", job)
        await engine.dispose()

    asyncio.run(go())


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW
    with TestClient(app) as test_client:
        yield test_client


def test_forecast_for_paulista(client: TestClient) -> None:
    _seed_forecast()
    lat, lon = PAULISTA
    response = client.get(f"/api/v1/weather/forecast?lat={lat}&lon={lon}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["kind"] == "FORECAST"
    assert body["point"]["distance_km"] < 25
    assert body["source"]["code"] == "open-meteo-forecast"
    assert "CC BY 4.0" in body["source"]["attribution"]

    # Agora = 15:00Z; na gravação: 30.2 °C e 0.1 mm nessa hora; vento 9.7 km/h -> 2.694 m/s
    assert body["now"]["valid_at"].startswith("2026-11-19T15:00:00")
    assert body["now"]["air_temperature"] == pytest.approx(30.2)
    assert body["now"]["precipitation"] == pytest.approx(0.1)
    assert body["now"]["wind_speed"] == pytest.approx(9.7 / 3.6, abs=1e-3)

    assert len(body["hourly"]) == 48
    assert body["hourly"][0]["valid_at"].startswith("2026-11-19T15:00:00")

    # Dias locais: a série gravada começa em 2026-11-19 (UTC) -> 7 dias a partir de hoje.
    assert len(body["daily"]) >= 6
    outlook = {o["hours"]: o for o in body["precipitation_outlook"]}
    assert set(outlook) == {1, 3, 24, 72}
    assert outlook[1]["total_mm"] == pytest.approx(0.1)
    assert outlook[3]["complete"] is True
    assert body["units"]["wind_speed"] == "m/s"


def test_far_location_is_404_problem(client: TestClient) -> None:
    _seed_forecast()
    response = client.get("/api/v1/weather/forecast?lat=-22.9&lon=-43.2")  # Rio de Janeiro
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "25 km" in response.json()["detail"]


def test_invalid_coordinates_are_422(client: TestClient) -> None:
    assert client.get("/api/v1/weather/forecast?lat=120&lon=0").status_code == 422

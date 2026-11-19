"""T018 — endpoints de fontes e estações contra o banco real (FR-030, FR-031, AC-021, AC-024)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.geo import BoundingBox
from app.ingestion.jobs import make_station_sync_job
from app.ingestion.pipeline import run_ingestion
from app.main import create_app
from app.tests.fixtures import INMET_STATIONS_SP, load

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

PAULISTA = (-23.5614, -46.6559)


def _seed_stations() -> None:
    async def fetcher(_url: str, _params: dict[str, str] | None) -> object:
        return load(INMET_STATIONS_SP)

    async def go() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        # Região ampla (RMSP + litoral) para ter estações de vários tipos no banco de teste.
        region = BoundingBox.parse("-47.5,-24.5,-45.0,-22.5")
        await run_ingestion(factory, "inmet-stations", make_station_sync_job(fetcher, region))
        await engine.dispose()

    asyncio.run(go())


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(get_settings())) as test_client:
        yield test_client


def test_sources_status_reports_missing_inmet_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("INMET_TOKEN", raising=False)
    get_settings.cache_clear()
    body = client.get("/api/v1/sources/status").json()
    by_code = {item["code"]: item for item in body["items"]}
    assert by_code["inmet-observations"]["freshness"] == "UNAVAILABLE"
    assert by_code["inmet-observations"]["reason"] == "missing_credentials"
    assert by_code["open-meteo-forecast"]["freshness"] == "UNKNOWN"
    assert "CC BY 4.0" in by_code["open-meteo-forecast"]["attribution"]


def test_sources_status_is_fresh_after_successful_sync(client: TestClient) -> None:
    _seed_stations()
    body = client.get("/api/v1/sources/status").json()
    stations = next(i for i in body["items"] if i["code"] == "inmet-stations")
    assert stations["freshness"] == "FRESH"
    assert stations["last_run_status"] == "SUCCESS"


def test_nearby_stations_are_ordered_by_distance(client: TestClient) -> None:
    _seed_stations()
    lat, lon = PAULISTA
    response = client.get(f"/api/v1/stations/nearby?lat={lat}&lon={lon}&radius_km=30")
    assert response.status_code == 200
    items = response.json()["items"]
    codes = [i["code"] for i in items]
    assert codes[:2] == ["A701", "A771"]
    assert 5 < items[0]["distance_km"] < 10
    assert items[0]["distance_km"] < items[1]["distance_km"]


def test_list_stations_with_bbox_and_status(client: TestClient) -> None:
    _seed_stations()
    body = client.get("/api/v1/stations?bbox=-46.83,-24.01,-46.36,-23.35").json()
    assert sorted(i["code"] for i in body["items"]) == ["A701", "A771"]
    assert body["total"] == 2
    faults = client.get("/api/v1/stations?status=FAULT").json()
    assert [i["code"] for i in faults["items"]] == ["A755"]


def test_invalid_bbox_is_a_422_problem(client: TestClient) -> None:
    response = client.get("/api/v1/stations?bbox=1,2,3")
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_observations_without_token_are_empty_and_explained(client: TestClient) -> None:
    _seed_stations()
    station_id = client.get("/api/v1/stations?bbox=-46.83,-24.01,-46.36,-23.35").json()["items"][0][
        "id"
    ]
    body = client.get(f"/api/v1/stations/{station_id}/observations").json()
    assert body["items"] == []
    assert body["availability"]["reason"] == "missing_credentials"


def test_observation_range_is_limited(client: TestClient) -> None:
    _seed_stations()
    station_id = client.get("/api/v1/stations").json()["items"][0]["id"]
    response = client.get(
        f"/api/v1/stations/{station_id}/observations"
        "?from=2026-01-01T00:00:00Z&to=2026-03-01T00:00:00Z"
    )
    assert response.status_code == 422


def test_unknown_station_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/stations/999999/observations").status_code == 404

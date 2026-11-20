"""T057/T058 — motor sobre dados reais gravados, gravação das execuções e rotas de risco.

Recortes reais: 6 setores do GeoSampa e a previsão da Open-Meteo de 2026-11-19 (um ponto,
-23.5149,-46.6105). Os setores de Campo Limpo e M'Boi Mirim ficam a mais de 25 km do ponto.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.deps import get_clock
from app.core.config import get_settings
from app.ingestion.jobs import make_forecast_job
from app.ingestion.pipeline import run_ingestion
from app.main import create_app
from app.models.tables import data_sources, risk_assessments, risk_runs, weather_forecasts
from app.risk.coefficients import ENGINE_VERSION
from app.services.risk import RiskRunSummary, compute_flood_risk
from app.tests.fixtures import OPEN_METEO_SP, load
from app.tests.integration.test_flood_sync import geosampa_fetcher, sync_all

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

FIXED_NOW = datetime(2026, 11, 19, 15, 20, tzinfo=UTC)


def forecast_payload(heavy_rain_mm: float | None = None) -> Any:
    payload = load(OPEN_METEO_SP)
    if heavy_rain_mm is not None:
        # resposta gravada em UTC (utc_offset_seconds = 0); 16:00Z cai na janela das 24 h
        index = payload["hourly"]["time"].index("2026-11-19T16:00")
        payload["hourly"]["precipitation"][index] = heavy_rain_mm
    return payload


async def _seed(
    f: async_sessionmaker[AsyncSession], heavy_rain_mm: float | None, forecast_age: timedelta
) -> None:
    await sync_all(f, geosampa_fetcher())

    async def fetcher(_url: str, _params: dict[str, str] | None) -> Any:
        return forecast_payload(heavy_rain_mm)

    await run_ingestion(f, "open-meteo-forecast", make_forecast_job(fetcher, [(-23.55, -46.63)]))
    async with f() as s:
        # frescor da previsão relativo ao relógio fixo, independente da data real do CI
        await s.execute(
            update(data_sources)
            .where(data_sources.c.code == "open-meteo-forecast")
            .values(last_success_at=FIXED_NOW - forecast_age, last_status="SUCCESS")
        )
        await s.commit()


def seed_and_compute(
    heavy_rain_mm: float | None = None, forecast_age: timedelta = timedelta(minutes=15)
) -> RiskRunSummary:
    async def go() -> RiskRunSummary:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _seed(factory, heavy_rain_mm, forecast_age)
            async with factory() as session:
                return await compute_flood_risk(session, FIXED_NOW)
        finally:
            await engine.dispose()

    return asyncio.run(go())


def query(statement: Any) -> list[Any]:
    async def go() -> list[Any]:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                return list((await conn.execute(statement)).all())
        finally:
            await engine.dispose()

    return asyncio.run(go())


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW
    with TestClient(app) as test_client:
        yield test_client


def by_code(client: TestClient) -> dict[str, dict[str, Any]]:
    body = client.get("/api/v1/risk/areas?limit=100").json()
    return {item["code"]: item for item in body["items"]}


def test_derived_susceptibility_from_real_layers(client: TestClient) -> None:
    summary = seed_and_compute()
    assert summary.status == "SUCCESS" and summary.sector_count == 6
    areas = by_code(client)
    derived = {
        code: (a["in_flood_extent_100y"], a["nearby_occurrences_12m"], a["susceptibility"])
        for code, a in areas.items()
    }
    assert derived == {
        "HMP-07-02": (True, 1, 3),
        "HMP-07-01": (True, 2, 2),
        "HMP-01-03": (True, 11, 4),
        "HCL-10-02": (False, 2, 2),
        "HMB-17-02": (False, 0, 4),
        "HAF-06-02": (False, 0, 1),
    }


def test_light_rain_is_low_and_far_sectors_are_unknown(client: TestClient) -> None:
    seed_and_compute()
    areas = by_code(client)
    categories = {code: a["category"] for code, a in areas.items()}
    assert categories == {
        "HMP-07-02": "LOW",
        "HMP-07-01": "LOW",
        "HMP-01-03": "LOW",
        "HAF-06-02": "LOW",
        "HCL-10-02": "UNKNOWN",  # ~26 km do único ponto de previsão
        "HMB-17-02": "UNKNOWN",
    }
    assert areas["HCL-10-02"]["unknown_reason"] == "NO_FORECAST_POINT"
    # histórico curto na resposta gravada: a chuva antecedente não é inventada
    assert areas["HMP-01-03"]["a72_mm"] is None


def test_heavy_rain_raises_categories_by_the_matrix(client: TestClient) -> None:
    seed_and_compute(heavy_rain_mm=30.0)
    areas = by_code(client)
    assert {code: a["category"] for code, a in areas.items() if a["category"] != "UNKNOWN"} == {
        "HMP-01-03": "HIGH",  # susc. 4, chuva forte
        "HMP-07-02": "HIGH",  # susc. 3
        "HMP-07-01": "MODERATE",  # susc. 2
        "HAF-06-02": "LOW",  # susc. 1
    }
    texts = [f["text"] for f in areas["HMP-01-03"]["factors"]]
    assert "Chuva forte prevista (30 mm em 1 h)" in texts
    # ordenação: maior categoria primeiro
    body = client.get("/api/v1/risk/areas?limit=2").json()
    assert [i["category"] for i in body["items"]] == ["HIGH", "HIGH"]
    assert body["total"] == 6


def test_ac063_stale_forecast_makes_everything_unknown(client: TestClient) -> None:
    seed_and_compute(heavy_rain_mm=30.0, forecast_age=timedelta(hours=12))
    summary = client.get("/api/v1/risk/summary").json()
    assert summary["run"]["forecast_freshness"] == "STALE"
    assert summary["counts"]["UNKNOWN"] == 6
    reasons = {a["unknown_reason"] for a in by_code(client).values()}
    assert reasons == {"FORECAST_STALE", "NO_FORECAST_POINT"}


def test_run_is_recorded_with_version_and_params() -> None:
    seed_and_compute()
    seed_and_compute()  # AC-066: mesma entrada, duas execuções gravadas
    runs = query(select(risk_runs.c.engine_version, risk_runs.c.status, risk_runs.c.params))
    assert len(runs) == 2
    assert {r.engine_version for r in runs} == {ENGINE_VERSION}
    assert runs[0].params["p1h_thresholds_mm"] == [10.0, 25.0, 50.0]
    assert runs[0].params["status"] == "experimental"
    per_run = query(
        select(risk_assessments.c.run_id, func.count()).group_by(risk_assessments.c.run_id)
    )
    assert sorted(n for _, n in per_run) == [6, 6]
    categories = query(
        select(
            risk_assessments.c.run_id, risk_assessments.c.sector_id, risk_assessments.c.category
        ).order_by(risk_assessments.c.sector_id, risk_assessments.c.run_id)
    )
    first = [(s, c) for r, s, c in categories if r == 1]
    second = [(s, c) for r, s, c in categories if r == 2]
    assert first == second


def test_summary_detail_and_disclaimer(client: TestClient) -> None:
    seed_and_compute(heavy_rain_mm=30.0)
    summary = client.get("/api/v1/risk/summary").json()
    assert summary["experimental"] is True
    assert "não é alerta oficial" in summary["disclaimer"].lower()
    assert "199" in summary["disclaimer"]
    assert summary["run"]["engine_version"] == ENGINE_VERSION
    assert summary["run"]["stale"] is False
    assert summary["counts"] == {
        "LOW": 1,
        "MODERATE": 1,
        "HIGH": 2,
        "CRITICAL": 0,
        "UNKNOWN": 2,
    }

    sector_id = by_code(client)["HMP-01-03"]["id"]
    detail = client.get(f"/api/v1/risk/areas/{sector_id}").json()
    assert detail["processes"] == ["ENCHENTE", "INUNDACAO"]
    assert detail["official_url"].startswith("https://geosampa")
    kinds = {i["name"]: i["kind"] for i in detail["inputs"]}
    assert kinds["Chuva prevista em 24 h"] == "FORECAST"
    assert kinds["Chuva estimada nas 72 h anteriores"] == "MODELED"
    assert len(detail["nearby_occurrences"]) == 11
    assert all(o["distance_m"] <= 300 for o in detail["nearby_occurrences"])
    assert client.get("/api/v1/risk/areas/999999").status_code == 404


def test_filters_and_nearest(client: TestClient) -> None:
    seed_and_compute(heavy_rain_mm=30.0)
    body = client.get("/api/v1/risk/areas?subprefecture=SAO MIGUEL PAULISTA").json()
    assert body["total"] == 3
    assert "SAO MIGUEL PAULISTA" in body["subprefectures"]
    assert client.get("/api/v1/risk/areas?category=HIGH").json()["total"] == 2
    assert client.get("/api/v1/risk/areas?category=ALERTA").status_code == 422

    near = client.get("/api/v1/risk/nearest?lat=-23.4746&lon=-46.4190").json()
    assert near["area"]["code"] == "HMP-01-03"
    assert near["distance_m"] < 100
    far = client.get("/api/v1/risk/nearest?lat=-23.55&lon=-46.63").json()
    assert far["area"] is None


def test_map_layers(client: TestClient) -> None:
    seed_and_compute(heavy_rain_mm=30.0)
    risk = client.get("/api/v1/map/layers/risk").json()
    assert risk["type"] == "FeatureCollection"
    assert len(risk["features"]) == 6
    assert "não é alerta oficial" in risk["disclaimer"].lower()
    feature = next(f for f in risk["features"] if f["properties"]["code"] == "HMP-01-03")
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert feature["properties"]["category"] == "HIGH"
    assert feature["properties"]["kind"] == "DERIVED"

    occ = client.get("/api/v1/map/layers/flood-occurrences").json()
    assert len(occ["features"]) == 16
    lon, lat = occ["features"][0]["geometry"]["coordinates"]
    assert -47 < lon < -46 and -24 < lat < -23


def test_no_sectors_records_failed_run() -> None:
    async def go() -> RiskRunSummary:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine)() as session:
                return await compute_flood_risk(session, FIXED_NOW)
        finally:
            await engine.dispose()

    summary = asyncio.run(go())
    assert summary.status == "FAILED"
    assert "nenhum setor" in (summary.error or "")
    rows = query(
        select(data_sources.c.last_status).where(data_sources.c.code == "flood-risk-engine")
    )
    assert rows[0][0] == "FAILED"


def test_retired_forecast_point_is_ignored(client: TestClient) -> None:
    """Ponto que saiu de FORECAST_POINTS não é usado depois da folga (nem no mapa)."""
    seed_and_compute()

    async def go() -> RiskRunSummary:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as s:
                await s.execute(
                    update(weather_forecasts).values(
                        issued_at=weather_forecasts.c.issued_at - timedelta(hours=6)
                    )
                )
                await s.commit()
            moved = forecast_payload(heavy_rain_mm=30.0)
            moved["latitude"], moved["longitude"] = -23.47, -46.42  # perto de São Miguel

            async def fetcher(_url: str, _params: dict[str, str] | None) -> Any:
                return moved

            await run_ingestion(
                factory, "open-meteo-forecast", make_forecast_job(fetcher, [(-23.47, -46.42)])
            )
            async with factory() as session:
                await session.execute(
                    update(data_sources)
                    .where(data_sources.c.code == "open-meteo-forecast")
                    .values(last_success_at=FIXED_NOW, last_status="SUCCESS")
                )
                await session.commit()
                return await compute_flood_risk(session, FIXED_NOW)
        finally:
            await engine.dispose()

    asyncio.run(go())
    areas = by_code(client)
    assert areas["HMP-01-03"]["category"] == "HIGH"  # usa o ponto novo, com chuva forte
    points = client.get("/api/v1/map/layers/forecast-points").json()["features"]
    assert [p["properties"]["point_key"] for p in points] == ["-23.4700,-46.4200"]

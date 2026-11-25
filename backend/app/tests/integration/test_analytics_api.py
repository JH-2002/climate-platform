"""T077 — catálogo, estatísticas, KPIs e insights com dados controlados (AC-082 a AC-084).

Reanálise sintética no ponto -23.57,-46.62 ("Centro"):
- novembros de 1991–2020: 2 mm/dia, com 30 mm no dia 15;
- novembro de 2026: 9 mm/dia de 1 a 12 e 0 mm de 13 a 18.
Assim: p95 diário de novembro = 2 mm; acumulado até 18/11 = 108 mm contra 64 mm de média
(169%); 6 dias secos seguidos, contra sequências históricas de 0 dia.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.deps import get_clock
from app.core.config import get_settings
from app.ingestion.archive_jobs import make_archive_backfill_job
from app.ingestion.jobs import make_forecast_job
from app.ingestion.pipeline import run_ingestion
from app.ingestion.reference_import import make_iag_import_job
from app.main import create_app
from app.tests.integration.test_flood_sync import geosampa_fetcher, sync_all
from app.tests.integration.test_risk_api import FIXED_NOW, forecast_payload

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

POINT = (-23.57, -46.62)
POINT_KEY = "-23.5700,-46.6200"


def synthetic_archive() -> dict[str, Any]:
    days: list[date] = [date(y, 11, d) for y in range(1991, 2021) for d in range(1, 31)]
    days += [date(2026, 11, d) for d in range(1, 19)]
    rain = []
    for day in days:
        if day.year == 2026:
            rain.append(9.0 if day.day <= 12 else 0.0)
        else:
            rain.append(30.0 if day.day == 15 else 2.0)
    return {
        "latitude": -23.585238,
        "longitude": -46.659637,
        "daily_units": {
            "precipitation_sum": "mm",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "temperature_2m_mean": "°C",
        },
        "daily": {
            "time": [d.isoformat() for d in days],
            "precipitation_sum": rain,
            "temperature_2m_max": [28.0] * len(days),
            "temperature_2m_min": [17.0] * len(days),
            "temperature_2m_mean": [22.0] * len(days),
        },
    }


def seed(heavy_rain_mm: float | None = None) -> None:
    async def archive(_url: str, _params: dict[str, str] | None) -> Any:
        return synthetic_archive()

    async def forecast(_url: str, _params: dict[str, str] | None) -> Any:
        return forecast_payload(heavy_rain_mm)

    async def go() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        f: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await run_ingestion(f, "iag-usp-rain-monthly", make_iag_import_job())
            await run_ingestion(
                f,
                "open-meteo-archive",
                make_archive_backfill_job(archive, [POINT], date(2026, 11, 18)),
            )
            await run_ingestion(
                f, "open-meteo-forecast", make_forecast_job(forecast, [(-23.55, -46.63)])
            )
            await sync_all(f, geosampa_fetcher())
        finally:
            await engine.dispose()

    asyncio.run(go())


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW
    with TestClient(app) as test_client:
        yield test_client


def test_catalog_lists_datasets_with_real_counts(client: TestClient) -> None:
    seed()
    body = client.get("/api/v1/analytics/datasets").json()
    by_id = {d["id"]: d for d in body}
    assert set(by_id) == {
        "iag-rain-monthly",
        "reanalysis-daily",
        "forecast-hourly",
        "flood-occurrences",
        "risk-assessments",
        "ingestion-runs",
    }
    iag = by_id["iag-rain-monthly"]
    assert (iag["records"], iag["period_start"], iag["period_end"]) == (1116, "1933-01", "2025-12")
    assert iag["kind"] == "OBSERVED" and "IAG/USP" in iag["attribution"]
    reanalysis = by_id["reanalysis-daily"]
    assert reanalysis["kind"] == "MODELED"
    assert reanalysis["locations"][0]["key"] == POINT_KEY
    assert reanalysis["locations"][0]["label"] == "Centro"
    assert "calendar" in reanalysis["visualizations"]
    assert "calendar" not in iag["visualizations"]
    assert by_id["flood-occurrences"]["records"] == 16


def test_ac082_describe(client: TestClient) -> None:
    seed()
    iag = client.get(
        "/api/v1/analytics/datasets/iag-rain-monthly/describe",
        params={"variable": "precipitation_month", "start": "1991-01-01", "end": "2020-12-31"},
    ).json()
    assert (iag["n"], iag["missing"], iag["coverage"]) == (360, 0, 1.0)
    assert iag["mean"] == pytest.approx(1559.2 / 12, abs=0.01)
    assert iag["maximum"] == 653.2  # janeiro de 2010
    nov = client.get(
        "/api/v1/analytics/datasets/reanalysis-daily/describe",
        params={
            "variable": "precipitation_sum",
            "location": POINT_KEY,
            "start": "2026-11-01",
            "end": "2026-11-20",
        },
    ).json()
    assert (nov["n"], nov["missing"], nov["expected"]) == (18, 2, 20)
    assert nov["median"] == 9.0 and nov["minimum"] == 0.0
    bad = client.get(
        "/api/v1/analytics/datasets/flood-occurrences/describe",
        params={"variable": "occurrences", "start": "2026-01-01", "end": "2026-02-01"},
    )
    assert bad.status_code == 422


def codes(client: TestClient) -> dict[str, dict[str, Any]]:
    body = client.get("/api/v1/analytics/insights").json()
    return {i["code"]: i for i in body["items"]}


def test_ac083_insights_follow_the_rules(client: TestClient) -> None:
    seed()
    found = codes(client)
    assert "IN-01" not in found  # previsão de ~1 mm < p95 de 2 mm
    assert found["IN-02"]["text"].startswith(
        "Novembro acumula 108 mm até ontem na região Centro, 169% da média"
    )
    assert "6 dias seguidos sem chuva relevante" in found["IN-03"]["text"]
    assert found["IN-06"]["text"].startswith("SAO MIGUEL PAULISTA concentra 87% das 15 ocorrências")
    assert found["IN-05"]["severity"] == "info"  # INMET: aguardando credencial
    for insight in found.values():
        assert insight["metrics"] and insight["sources"]
        assert insight["rules_version"].endswith("experimental")


def test_ac083_heavy_forecast_raises_in01(client: TestClient) -> None:
    seed(heavy_rain_mm=30.0)
    insight = codes(client)["IN-01"]
    assert insight["severity"] == "atencao"
    assert "na região Centro" in insight["text"] and "p95 = 2 mm" in insight["text"]
    kinds = [m["kind"] for m in insight["metrics"]]
    assert kinds == ["FORECAST", "MODELED"]
    body = client.get("/api/v1/analytics/insights").json()
    assert body["items"][0]["severity"] == "atencao"  # atenção vem primeiro


def test_ac084_kpis_have_source_kind_and_link(client: TestClient) -> None:
    seed()
    body = client.get("/api/v1/analytics/kpis").json()
    by_code = {k["code"]: k for k in body["items"]}
    assert set(by_code) == {
        "forecast_rain_24h",
        "month_to_date_rain",
        "risk_high_sectors",
        "occurrences_30d",
        "sources_fresh",
        "ingestion_failure_rate_7d",
    }
    for kpi in body["items"]:
        assert kpi["source"] and kpi["kind"] and kpi["href"].startswith("/")
    mtd = by_code["month_to_date_rain"]
    assert mtd["value"] == 108.0 and mtd["kind"] == "MODELED"
    assert mtd["detail"].startswith("169% da média dos mesmos 18 dias")
    assert by_code["forecast_rain_24h"]["value"] == pytest.approx(1.0)
    assert by_code["risk_high_sectors"]["available"] is False  # nenhuma execução ainda
    occ = by_code["occurrences_30d"]
    assert occ["value"] == 0.0 and occ["detail"] == "registro mais recente na base: 21/09/2026"
    assert client.get("/api/v1/analytics/kpis").headers["cache-control"] == "public, max-age=60"


def test_insights_without_reanalysis_explain_the_gap(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/insights").json()
    assert any("aguardam a carga inicial" in note for note in body["notes"])
    assert {i["code"] for i in body["items"]} <= {"IN-05"}

"""T080, T083, T084 — séries, comparação, CSV, climatologia, distribuição, ranking,
tendências, histórico do risco e saúde das fontes (AC-085, AC-087, AC-088).

Usa os mesmos dados de `test_analytics_api` (IAG real + reanálise sintética).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.deps import get_clock
from app.core.config import get_settings
from app.main import create_app
from app.services.risk import compute_flood_risk
from app.tests.integration.test_analytics_api import POINT_KEY, seed
from app.tests.integration.test_risk_api import FIXED_NOW

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

BASE = "/api/v1/analytics"


@pytest.fixture
def client() -> Iterator[TestClient]:
    seed()
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW
    with TestClient(app) as test_client:
        yield test_client


def series(client: TestClient, **params: Any) -> Any:
    return client.get(f"{BASE}/series", params=params)


def test_iag_monthly_against_normal(client: TestClient) -> None:
    body = series(
        client,
        dataset="iag-rain-monthly",
        variable="precipitation_month",
        start="2025-01-01",
        end="2025-12-31",
        grain="month",
        agg="sum",
        compare="normal",
    ).json()
    assert body["kind"] == "OBSERVED" and body["unit"] == "mm"
    assert len(body["points"]) == 12
    april = body["points"][3]
    assert (april["start"], april["value"]) == ("2025-04-01", 186.9)
    assert april["reference"] == pytest.approx(82.6, abs=0.05)
    assert body["reference_label"] == "Normal 1991–2020 (medida)"
    assert "IAG/USP" in body["attribution"]


def test_iag_annual_sum_matches_published_normal(client: TestClient) -> None:
    body = series(
        client,
        dataset="iag-rain-monthly",
        variable="precipitation_month",
        start="1991-01-01",
        end="2020-12-31",
        grain="year",
        agg="sum",
        compare="normal",
    ).json()
    assert len(body["points"]) == 30
    assert body["points"][0]["value"] == pytest.approx(1918.7)
    assert body["points"][0]["reference"] == pytest.approx(1559.2, abs=0.1)
    assert all(p["coverage"] == 1.0 for p in body["points"])


def test_daily_coverage_and_partial_month(client: TestClient) -> None:
    days = series(
        client,
        dataset="reanalysis-daily",
        variable="precipitation_sum",
        location=POINT_KEY,
        start="2026-11-01",
        end="2026-11-20",
        grain="day",
        agg="sum",
    ).json()["points"]
    assert len(days) == 20
    assert days[11]["value"] == 9.0 and days[12]["value"] == 0.0
    assert days[19]["value"] is None and days[19]["insufficient"] is True
    month = series(
        client,
        dataset="reanalysis-daily",
        variable="precipitation_sum",
        location=POINT_KEY,
        start="2026-11-01",
        end="2026-11-30",
        grain="month",
        agg="sum",
        compare="normal",
    ).json()
    point = month["points"][0]
    assert (point["value"], point["n"], point["expected"]) == (108.0, 18, 30)
    assert point["partial"] is True and point["coverage"] == 0.6
    assert point["reference"] == pytest.approx(88.0)  # 29 × 2 mm + 30 mm
    assert month["reference_label"] == "Normal 1991–2020 (reanálise)"


def test_ac085_incompatible_aggregation_and_grain(client: TestClient) -> None:
    bad = series(
        client,
        dataset="reanalysis-daily",
        variable="air_temperature_max",
        location=POINT_KEY,
        start="2026-11-01",
        end="2026-11-18",
        grain="day",
        agg="sum",
    )
    assert bad.status_code == 422
    assert "não tem significado físico" in bad.text
    grain = series(
        client,
        dataset="iag-rain-monthly",
        variable="precipitation_month",
        start="2020-01-01",
        end="2020-02-01",
        grain="day",
        agg="sum",
    )
    assert grain.status_code == 422 and "agrupamento day indisponível" in grain.text
    normal_daily = series(
        client,
        dataset="reanalysis-daily",
        variable="precipitation_sum",
        location=POINT_KEY,
        start="2026-11-01",
        end="2026-11-18",
        grain="day",
        agg="sum",
        compare="normal",
    )
    assert normal_daily.status_code == 422


def test_previous_period_comparison(client: TestClient) -> None:
    body = series(
        client,
        dataset="reanalysis-daily",
        variable="precipitation_sum",
        location=POINT_KEY,
        start="2026-11-11",
        end="2026-11-18",
        grain="day",
        agg="sum",
        compare="previous_period",
    ).json()
    assert [p["value"] for p in body["points"]] == [9.0, 9.0, 0, 0, 0, 0, 0, 0]
    assert [p["reference"] for p in body["points"]] == [9.0] * 8
    assert body["reference_label"].startswith("Período anterior (03/11/2026–10/11/2026)")


def test_ac087_csv_has_metadata_and_same_numbers(client: TestClient) -> None:
    params = {
        "dataset": "reanalysis-daily",
        "variable": "precipitation_sum",
        "location": POINT_KEY,
        "start": "2026-11-10",
        "end": "2026-11-14",
        "grain": "day",
        "agg": "sum",
    }
    response = client.get(f"{BASE}/series.csv", params=params)
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.splitlines()
    assert "# tipo: MODELED" in lines
    assert any(line.startswith("# atribuicao: Reanálise: Open-Meteo.com") for line in lines)
    assert any(line.startswith("# aviso: Estimativa de modelo") for line in lines)
    rows = [line for line in lines if not line.startswith("#")]
    assert rows[0].startswith("inicio,valor,unidade")
    assert rows[1:] == [
        "2026-11-10,9.0,mm,,1,1,1.0,não",
        "2026-11-11,9.0,mm,,1,1,1.0,não",
        "2026-11-12,9.0,mm,,1,1,1.0,não",
        "2026-11-13,0.0,mm,,1,1,1.0,não",
        "2026-11-14,0.0,mm,,1,1,1.0,não",
    ]


def test_climatology_iag_matches_published(client: TestClient) -> None:
    body = client.get(
        f"{BASE}/climatology",
        params={"dataset": "iag-rain-monthly", "variable": "precipitation_month"},
    ).json()
    assert body["period"] == "1991-2020"
    means = [m["mean"] for m in body["months"]]
    for computed, published in zip(means, body["published"], strict=True):
        assert computed == pytest.approx(published, abs=0.5)
    assert body["annual_mean"] == pytest.approx(body["published_annual"], abs=0.5)
    assert body["months"][0]["years_used"] == 30
    assert body["months"][0]["p25"] < body["months"][0]["mean"] < body["months"][0]["p90"]


def test_distribution_and_ranking(client: TestClient) -> None:
    dist = client.get(
        f"{BASE}/distribution",
        params={"location": POINT_KEY, "start": "2026-11-01", "end": "2026-11-18"},
    ).json()
    assert (dist["days"], dist["wet_days"]) == (18, 12)
    by_low = {b["low"]: b["count"] for b in dist["bins"]}
    assert by_low[5.0] == 12
    assert dist["extremes"][0]["value"] == 9.0
    ranking = client.get(
        f"{BASE}/ranking",
        params={
            "dataset": "flood-occurrences",
            "variable": "occurrences",
            "agg": "count",
            "start": "2026-01-01",
            "end": "2026-12-31",
        },
    ).json()
    assert [(i["key"], i["value"]) for i in ranking["items"]] == [
        ("SAO MIGUEL PAULISTA", 13.0),
        ("ERMELINO MATARAZZO", 2.0),
        ("VILA PRUDENTE", 1.0),
    ]


def test_ac088_trends(client: TestClient) -> None:
    body = client.get(f"{BASE}/trends").json()
    assert len(body["annual"]) == 93 and body["kind"] == "OBSERVED"
    assert body["moving_average_10y"][0]["year"] == 1942
    assert [n["period"] for n in body["normals"]] == ["1933-1960", "1961-1990", "1991-2020"]
    assert all(abs(n["difference"]) <= 0.5 for n in body["normals"])
    assert body["wettest"][0] == {"year": 1983, "value": 2236.0}
    assert body["driest"][0] == {"year": 1933, "value": 849.8}
    assert "não indica a causa" in body["note"]
    assert "tendência" not in body["note"].lower()


def test_risk_history_and_sources_health(client: TestClient) -> None:
    async def compute() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine)() as session:
                await compute_flood_risk(session, FIXED_NOW)
        finally:
            await engine.dispose()

    asyncio.run(compute())
    history = client.get(f"{BASE}/risk-history").json()
    assert len(history["runs"]) == 1
    assert sum(history["runs"][0]["counts"].values()) == 6
    names = [g["name"] for g in history["by_subprefecture"]]
    assert "SAO MIGUEL PAULISTA" in names
    assert "não é alerta oficial" in history["engine_note"]

    health = {s["code"]: s for s in client.get(f"{BASE}/sources-health").json()}
    iag = health["iag-usp-rain-monthly"]
    assert iag["runs_7d"] >= 1 and iag["availability_7d"] == 1.0
    assert iag["coverage"] == "93 anos completos"
    assert health["geosampa-risk-sectors"]["coverage"] == "6 setores ativos"
    assert health["inmet-observations"]["reason"] == "missing_credentials"

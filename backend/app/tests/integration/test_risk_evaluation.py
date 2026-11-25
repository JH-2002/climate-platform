"""Spec 015 — retroteste do motor com setores e ocorrências reais gravados do GeoSampa.

Ocorrências do recorte: inundação em São Miguel Paulista em 2026-09-12 e alagamentos de abril e
setembro. A previsão arquivada é sintética: sem chuva, salvo 60 mm às 18 h UTC de 2026-09-12.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.ingestion.forecast_archive_jobs import make_forecast_archive_job
from app.ingestion.pipeline import run_ingestion
from app.main import create_app
from app.services.risk_evaluation import EvaluationSummary, compute_risk_evaluation
from app.tests.integration.test_flood_sync import geosampa_fetcher, sync_all

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

NOW = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
POINTS = [(-23.55, -46.63)]
HEAVY = "2026-09-12T18:00"


async def archive_fetcher(_url: str, params: dict[str, str] | None) -> Any:
    assert params is not None
    start, end = date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
    hours = int((end - start).days + 1) * 24
    times = [
        (datetime.combine(start, datetime.min.time()) + timedelta(hours=h)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        for h in range(hours)
    ]
    rain = [60.0 if t == HEAVY else 0.0 for t in times]
    return {
        "hourly_units": {"precipitation": "mm"},
        "hourly": {"time": times, "precipitation": rain},
    }


def seed_and_evaluate() -> EvaluationSummary:
    async def go() -> EvaluationSummary:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        f: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await sync_all(f, geosampa_fetcher())
            outcome = await run_ingestion(
                f,
                "open-meteo-historical-forecast",
                make_forecast_archive_job(archive_fetcher, POINTS, date(2026, 9, 19)),
            )
            assert outcome.status == "SUCCESS", outcome.error
            async with f() as session:
                return await compute_risk_evaluation(session, NOW, POINTS)
        finally:
            await engine.dispose()

    return asyncio.run(go())


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(get_settings())) as test_client:
        yield test_client


def test_sem_avaliacao_a_rota_explica(client: TestClient) -> None:
    response = client.get("/api/v1/analytics/risk-evaluation")
    assert response.status_code == 404
    assert "ainda não foi calculada" in response.json()["detail"]


def test_retroteste_acerta_a_inundacao_com_chuva_forte(client: TestClient) -> None:
    summary = seed_and_evaluate()
    assert summary.status == "SUCCESS", summary.error
    # 2026-01-04 (72 h antecedentes desde 01-01) até a véspera de NOW
    assert summary.days == (date(2026, 9, 19) - date(2026, 1, 4)).days + 1

    body = client.get("/api/v1/analytics/risk-evaluation").json()
    table = body["contingency"]
    assert table["hits"] >= 1  # 2026-09-12 em São Miguel Paulista
    assert table["units"] == summary.units and table["events"] == summary.events
    assert body["decision"] == "HIGH_OR_CRITICAL"
    assert [row["factor"] for row in body["calibration"]] == [
        0.5,
        0.6,
        0.7,
        0.8,
        0.9,
        1.0,
        1.1,
        1.2,
        1.3,
        1.4,
        1.5,
    ]
    current = next(row for row in body["calibration"] if row["factor"] == 1.0)
    assert current["hits"] == table["hits"]
    assert {r["category"] for r in body["reliability"]} == {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert body["monthly"][0]["month"] == "2026-01"
    assert body["current_thresholds"] == {
        "p1h_mm": [10.0, 25.0, 50.0],
        "p24_mm": [30.0, 60.0, 100.0],
    }
    # setores fora da grade (> 25 km) ficam desconhecidos: Campo Limpo e M'Boi Mirim saem da conta
    assert body["subprefectures"] >= 3

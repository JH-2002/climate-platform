"""Spec 007, Parte A — simulação sobre os setores reais gravados (recorte de 6 setores)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.v1.deps import get_clock
from app.core.config import get_settings
from app.main import create_app
from app.models.tables import risk_runs, simulation_results, simulation_runs
from app.tests.integration.test_risk_api import FIXED_NOW, query, seed_and_compute

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

CITYWIDE_60 = {"total_mm": 60, "duration_h": 1, "pattern": "CONSTANT", "antecedent_mm": 0}


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW
    with TestClient(app) as test_client:
        yield test_client


def simulate(client: TestClient, body: dict[str, Any] = CITYWIDE_60) -> dict[str, Any]:
    response = client.post("/api/v1/simulation/runs", json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def sectors(client: TestClient, run_id: str) -> dict[str, dict[str, Any]]:
    body = client.get(f"/api/v1/simulation/runs/{run_id}/sectors?limit=100").json()
    return {item["code"]: item for item in body["items"]}


def test_presets_list_origin(client: TestClient) -> None:
    body = client.get("/api/v1/simulation/presets").json()
    assert [p["code"] for p in body][:1] == ["pancada-de-verao"]
    assert all(p["origin"] for p in body)


def test_citywide_storm_follows_the_risk_matrix(client: TestClient) -> None:
    seed_and_compute()
    run = simulate(client)
    assert run["kind"] == "SIMULATED" and run["mode"] == "SIMULATION"
    assert run["banner"].startswith("SIMULAÇÃO")
    assert run["counts"] == {"CRITICAL": 3, "HIGH": 2, "MODERATE": 1, "LOW": 0, "UNKNOWN": 0}
    categories = {code: s["category"] for code, s in sectors(client, run["id"]).items()}
    assert categories == {
        "HMP-07-02": "CRITICAL",
        "HMP-01-03": "CRITICAL",
        "HMB-17-02": "CRITICAL",
        "HMP-07-01": "HIGH",
        "HCL-10-02": "HIGH",
        "HAF-06-02": "MODERATE",
    }
    # comparação: 4 setores baixos no real sobem; 2 desconhecidos no real não são comparados
    comparison = run["comparison"]
    assert (comparison["raised"], comparison["lowered"], comparison["not_comparable"]) == (4, 0, 2)
    assert comparison["real_run"] is not None and comparison["real_counts"]["LOW"] == 4
    assert run["sectors_changed"] is False and run["sector_count"] == 6
    assert "60 mm em 1 hora" in run["scenario_text"]


def test_simulation_does_not_touch_real_risk(client: TestClient) -> None:
    """AC-103: Risco, Análises e Visão geral não mudam."""
    seed_and_compute()
    before = [client.get(p).json() for p in ("/api/v1/risk/summary", "/api/v1/risk/areas")]
    kpis_before = client.get("/api/v1/analytics/kpis").json()
    simulate(client)
    after = [client.get(p).json() for p in ("/api/v1/risk/summary", "/api/v1/risk/areas")]
    assert after == before
    assert client.get("/api/v1/analytics/kpis").json() == kpis_before
    assert query(select(func.count()).select_from(risk_runs))[0][0] == 1


def test_cell_reaches_only_nearby_sectors(client: TestClient) -> None:
    seed_and_compute()
    detail = client.get("/api/v1/risk/areas?limit=100").json()["items"]
    target = next(a for a in detail if a["code"] == "HMP-01-03")
    center = client.get(f"/api/v1/risk/areas/{target['id']}").json()
    run = simulate(
        client,
        {
            **CITYWIDE_60,
            "cell": {
                "latitude": center["latitude"],
                "longitude": center["longitude"],
                "radius_km": 2,
            },
        },
    )
    by_code = sectors(client, run["id"])
    assert by_code["HMP-01-03"]["category"] == "CRITICAL"
    assert by_code["HMP-01-03"]["rain_factor"] == 1.0
    far = by_code["HCL-10-02"]  # Campo Limpo, do outro lado da cidade
    assert far["rain_factor"] == 0.0 and far["category"] == "LOW" and far["distance_km"] > 20


def test_sector_detail_and_map_layer(client: TestClient) -> None:
    seed_and_compute()
    run = simulate(client)
    item = sectors(client, run["id"])["HMP-01-03"]
    assert item["real_category"] == "LOW"
    detail = client.get(f"/api/v1/simulation/runs/{run['id']}/sectors/{item['id']}").json()
    texts = [f["text"] for f in detail["factors"]]
    assert any("no cenário" in t for t in texts) and not any("prevista" in t for t in texts)
    layer = client.get(f"/api/v1/map/layers/simulation/{run['id']}").json()
    assert len(layer["features"]) == 6
    assert {f["properties"]["kind"] for f in layer["features"]} == {"SIMULATED"}
    assert layer["attribution"].startswith("SIMULAÇÃO")


def test_same_scenario_same_result(client: TestClient) -> None:
    """AC-101 pela API: duas execuções, setores idênticos."""
    seed_and_compute()
    first, second = simulate(client), simulate(client)
    assert first["id"] != second["id"]
    assert sectors(client, first["id"]) == sectors(client, second["id"])


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({**CITYWIDE_60, "total_mm": 400}, "Chuva total"),
        ({**CITYWIDE_60, "duration_h": 30}, "Duração"),
        (
            {**CITYWIDE_60, "cell": {"latitude": -22.9, "longitude": -43.2, "radius_km": 5}},
            "Latitude",
        ),
        ({**CITYWIDE_60, "preset": "inexistente"}, "Cenário pronto"),
    ],
)
def test_limits_return_422(client: TestClient, body: dict[str, Any], message: str) -> None:
    seed_and_compute()
    response = client.post("/api/v1/simulation/runs", json=body)
    assert response.status_code == 422 and message in response.json()["detail"]


def test_without_sectors_returns_503(client: TestClient) -> None:
    response = client.post("/api/v1/simulation/runs", json=CITYWIDE_60)
    assert response.status_code == 503


def test_unknown_run_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/simulation/runs/{uuid.uuid4()}").status_code == 404
    assert client.get(f"/api/v1/map/layers/simulation/{uuid.uuid4()}").status_code == 404


def test_retention_drops_runs_older_than_30_days(client: TestClient) -> None:
    seed_and_compute()
    old = simulate(client)
    client.app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW + timedelta(days=31)  # type: ignore[attr-defined]
    new = simulate(client)
    ids = {str(r[0]) for r in query(select(simulation_runs.c.id))}
    assert ids == {new["id"]}
    assert old["id"] not in ids
    remaining = query(select(func.count()).select_from(simulation_results))[0][0]
    assert remaining == 6


def test_subprefecture_centers(client: TestClient) -> None:
    seed_and_compute()
    centers = client.get("/api/v1/simulation/centers").json()
    names = {c["name"] for c in centers}
    assert {"SAO MIGUEL PAULISTA", "CAMPO LIMPO"} <= names
    assert all(-24 < c["latitude"] < -23 and c["sectors"] >= 1 for c in centers)


# --- Parte B: variações com seed, modo HYBRID e histórico ---------------------------------

ENSEMBLE = {**CITYWIDE_60, "members": 20, "intensity_pct": 30, "shift_km": 0, "seed": 42}


def test_ensemble_probabilities_and_repeat(client: TestClient) -> None:
    """AC-104 pela API e FR-110: repetir com o mesmo seed dá resultado idêntico."""
    seed_and_compute()
    first = simulate(client, ENSEMBLE)
    assert first["seed"] == 42 and first["members"] == 20
    assert first["ensemble"]["members"] == 20
    assert first["ensemble"]["p10"] <= first["ensemble"]["mean"] <= first["ensemble"]["p90"]
    probs = {
        code: (s["p_high"], s["p_critical"]) for code, s in sectors(client, first["id"]).items()
    }
    assert all(p is not None and 0 <= p <= 1 for pair in probs.values() for p in pair)
    # 60 mm/h ± 30%: R1 (moderado no centro) nunca chega a alto; R4 sempre chega
    assert probs["HAF-06-02"][0] == 0.0 and probs["HMP-01-03"][0] == 1.0
    again = simulate(client, {**ENSEMBLE, "repeat_of": first["id"]})
    check = again["repeat_check"]
    assert check["original_id"] == first["id"]
    assert check["identical_results"] is True
    assert check["same_engine_versions"] and check["same_sectors"]
    assert check["same_forecast"] is None  # sem previsão no modo SIMULATION
    # seed 7: 13 de 20 variações passam de 50 mm/h, contra 16 com o seed 42 (setores R2 e R3)
    other = simulate(client, {**ENSEMBLE, "seed": 7, "repeat_of": first["id"]})
    assert other["repeat_check"]["identical_results"] is False


def test_seed_is_drawn_and_recorded_when_missing(client: TestClient) -> None:
    seed_and_compute()
    run = simulate(client, {**ENSEMBLE, "seed": None})
    assert isinstance(run["seed"], int) and run["seed"] >= 0
    assert "20 variações" in run["scenario_text"]


def test_hybrid_without_change_reproduces_the_real_estimate(client: TestClient) -> None:
    """Previsão real × 100%, sem chuva extra: as categorias batem com o risco real."""
    seed_and_compute()
    run = simulate(client, {"mode": "HYBRID", "multiplier": 1.0})
    assert run["mode"] == "HYBRID" and run["banner"].startswith("SIMULAÇÃO A PARTIR")
    assert run["forecast_issued_at"] is not None
    assert "previsão real × 100%" in run["scenario_text"]
    items = sectors(client, run["id"])
    assert {code: s["category"] for code, s in items.items()} == {
        code: s["real_category"] for code, s in items.items()
    }
    assert run["counts"]["UNKNOWN"] == 2  # sem ponto de previsão a até 25 km (BR-103)


def test_hybrid_adds_storm_on_top_of_forecast(client: TestClient) -> None:
    seed_and_compute()
    run = simulate(client, {**CITYWIDE_60, "mode": "HYBRID", "multiplier": 1.0, "add_storm": True})
    categories = {code: s["category"] for code, s in sectors(client, run["id"]).items()}
    assert categories["HMP-01-03"] == "CRITICAL"
    assert categories["HCL-10-02"] == "UNKNOWN"  # sem previsão, mesmo com a chuva do cenário


def test_hybrid_refused_with_stale_forecast(client: TestClient) -> None:
    """AC-105: previsão vencida → 409; o modo só com o cenário continua."""
    seed_and_compute(forecast_age=timedelta(hours=12))
    response = client.post("/api/v1/simulation/runs", json={"mode": "HYBRID", "multiplier": 2})
    assert response.status_code == 409
    assert "desatualizada" in response.json()["detail"]
    assert client.post("/api/v1/simulation/runs", json=CITYWIDE_60).status_code == 201


def test_hybrid_limits(client: TestClient) -> None:
    seed_and_compute()
    response = client.post("/api/v1/simulation/runs", json={"mode": "HYBRID", "multiplier": 4})
    assert response.status_code == 422 and "Multiplicador" in response.json()["detail"]
    response = client.post("/api/v1/simulation/runs", json={**ENSEMBLE, "members": 120})
    assert response.status_code == 422 and "variações" in response.json()["detail"]


def test_history_lists_recent_runs(client: TestClient) -> None:
    seed_and_compute()
    first = simulate(client)
    second = simulate(client, {"mode": "HYBRID", "multiplier": 2.0})
    history = client.get("/api/v1/simulation/runs?limit=5").json()
    assert [h["id"] for h in history][:2] == [second["id"], first["id"]] or {
        h["id"] for h in history
    } == {first["id"], second["id"]}
    by_id = {h["id"]: h for h in history}
    assert by_id[first["id"]]["high_or_above"] == 5
    assert by_id[second["id"]]["mode"] == "HYBRID"


def test_repeat_of_unknown_run_returns_404(client: TestClient) -> None:
    seed_and_compute()
    response = client.post(
        "/api/v1/simulation/runs", json={**CITYWIDE_60, "repeat_of": str(uuid.uuid4())}
    )
    assert response.status_code == 404


def test_purge_task_logic(client: TestClient) -> None:
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.services.simulation import purge_old_runs

    seed_and_compute()
    simulate(client)

    async def go() -> int:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine)() as session:
                removed = await purge_old_runs(session, FIXED_NOW + timedelta(days=31))
                await session.commit()
                return removed
        finally:
            await engine.dispose()

    assert asyncio.run(go()) == 1
    assert query(select(func.count()).select_from(simulation_runs))[0][0] == 0

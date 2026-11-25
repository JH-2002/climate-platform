"""Spec 010, Parte A — central de relatórios com o banco e os dados das fixtures.

A geração é chamada direto no serviço (o worker do Celery só a dispara).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.v1.deps import get_clock
from app.api.v1.reports import get_enqueuer
from app.core.config import get_settings
from app.main import create_app
from app.models.tables import report_requests
from app.services import reports as report_service
from app.tests.integration.test_analytics_api import POINT_KEY, seed
from app.tests.integration.test_flood_sync import sessions
from app.tests.integration.test_risk_api import FIXED_NOW, query, seed_and_compute
from app.tests.integration.test_simulation_api import simulate
from app.tests.unit.test_report_writers import _streams

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW

    async def no_worker(_request_id: str) -> None:
        return None

    app.dependency_overrides[get_enqueuer] = lambda: no_worker
    with TestClient(app) as test_client:
        yield test_client


def generate(request_id: str, offset: timedelta = timedelta(0)) -> str:
    async def go() -> str:
        async with sessions() as factory, factory() as session:
            return await report_service.generate(session, uuid.UUID(request_id), FIXED_NOW + offset)

    return asyncio.run(go())


def housekeeping(offset: timedelta) -> tuple[int, int]:
    async def go() -> tuple[int, int]:
        async with sessions() as factory, factory() as session:
            return await report_service.housekeeping(session, FIXED_NOW + offset)

    return asyncio.run(go())


def ask(client: TestClient, kind: str, fmt: str, params: dict[str, Any] | None = None) -> Any:
    response = client.post(
        "/api/v1/reports", json={"type": kind, "format": fmt, "params": params or {}}
    )
    assert response.status_code == 202, response.text
    return response.json()


def produce(client: TestClient, kind: str, fmt: str, params: dict[str, Any] | None = None) -> Any:
    created = ask(client, kind, fmt, params)
    assert created["status"] == "QUEUED"
    assert generate(created["id"]) == "DONE"
    status = client.get(f"/api/v1/reports/{created['id']}").json()
    assert status["status"] == "DONE", status
    download = client.get(status["download_url"])
    assert download.status_code == 200
    return status, download


def test_types_catalog(client: TestClient) -> None:
    body = client.get("/api/v1/reports/types").json()
    assert [t["code"] for t in body] == ["situacao", "risco", "alertas", "chuva", "simulacao"]


def test_ac150_situation_pdf(client: TestClient) -> None:
    seed_and_compute(heavy_rain_mm=30.0)
    status, download = produce(client, "situacao", "pdf")
    assert download.headers["content-type"] == "application/pdf"
    disposition = download.headers["content-disposition"]
    assert disposition == 'attachment; filename="situacao_2026-11-19_1220.pdf"'
    assert download.content.startswith(b"%PDF-1.4")
    assert status["bytes"] == len(download.content)
    pages = _streams(download.content)
    assert all("Estimativa experimental do sistema" in page for page in pages)
    text = "\n".join(pages)
    assert "HMP-01-03" in text  # setor em alto com a chuva forte
    assert "Open-Meteo.com \\(CC BY 4.0\\)" in text


def test_ac151_risk_csv_has_one_line_per_sector(client: TestClient) -> None:
    seed_and_compute(heavy_rain_mm=30.0)
    _, download = produce(client, "risco", "csv")
    assert download.headers["content-type"].startswith("text/csv")
    text = download.content.decode("utf-8-sig")
    lines = [line for line in text.split("\r\n") if line]
    comments = [line for line in lines if line.startswith("#")]
    assert any(line.startswith("# Fonte: GeoSampa") for line in comments)
    assert "# Tipo do dado: calculado pelo sistema" in comments
    data = [line for line in lines if not line.startswith("#")]
    assert data[0].startswith("Setor;Área;Subprefeitura;Grau;Risco estimado;Chuva máx. 1 h (mm)")
    assert len(data) - 1 == 6
    high = next(line for line in data if line.startswith("HMP-01-03;"))
    assert ";Alto;30,0;" in high  # vírgula decimal


def test_risk_filter_and_json(client: TestClient) -> None:
    seed_and_compute()
    _, download = produce(client, "risco", "json", {"subprefecture": "SAO MIGUEL PAULISTA"})
    doc = json.loads(download.content)
    assert doc["metadata"]["params"] == {"subprefecture": "SAO MIGUEL PAULISTA"}
    table = next(s for s in doc["sections"] if s["type"] == "table")
    assert {row["subprefecture"] for row in table["rows"]} == {"Sao Miguel Paulista"}
    assert len(table["rows"]) == 3


def test_ac152_simulation_is_labelled_everywhere(client: TestClient) -> None:
    seed_and_compute()
    run = simulate(client)
    banner = "SIMULAÇÃO — CENÁRIO HIPOTÉTICO, NÃO É PREVISÃO NEM ALERTA"
    status, pdf = produce(client, "simulacao", "pdf", {"simulation_id": run["id"]})
    assert status["mode"] == "SIMULATION"
    assert pdf.headers["content-disposition"].startswith('attachment; filename="simulacao_')
    assert all("SIMULA\\307\\303O" in page for page in _streams(pdf.content))
    _, csv_file = produce(client, "simulacao", "csv", {"simulation_id": run["id"]})
    assert csv_file.content.decode("utf-8-sig").split("\r\n")[0] == f"# {banner}"
    _, json_file = produce(client, "simulacao", "json", {"simulation_id": run["id"]})
    metadata = json.loads(json_file.content)["metadata"]
    assert metadata["mode"] == "SIMULATION" and metadata["banner"] == banner


def test_rain_report(client: TestClient) -> None:
    seed()
    params = {"point": POINT_KEY, "since": "2026-11-01", "until": "2026-11-30", "grain": "month"}
    status, download = produce(client, "chuva", "json", params)
    assert status["params"]["until"] == "2026-11-18"  # até ontem
    doc = json.loads(download.content)
    table = next(s for s in doc["sections"] if s["type"] == "table")
    (row,) = table["rows"]
    assert row["value"] == pytest.approx(108.0)  # 12 dias de 9 mm
    assert row["reference"] == pytest.approx(88.0)  # normal de novembro (sintética)
    daily = {**params, "grain": "day"}
    _, csv_file = produce(client, "chuva", "csv", daily)
    data = [
        line
        for line in csv_file.content.decode("utf-8-sig").split("\r\n")
        if line and not line.startswith("#")
    ]
    assert len(data) - 1 == 18


def test_alerts_report_without_alerts(client: TestClient) -> None:
    _, download = produce(client, "alertas", "pdf", {"since": "2026-11-12", "until": "2026-11-19"})
    text = "\n".join(_streams(download.content))
    assert "Nenhum alerta oficial." in text


def test_ac153_invalid_params_create_nothing(client: TestClient) -> None:
    seed_and_compute()
    cases = [
        ("alertas", {"since": "2026-01-01", "until": "2026-11-19"}, "90 dias"),
        ("alertas", {"since": "2026-11-19"}, "Até"),
        ("risco", {"subprefecture": "ATLANTIDA"}, "Subprefeitura"),
        ("simulacao", {"simulation_id": str(uuid.uuid4())}, "Simulação não encontrada"),
        ("simulacao", {"simulation_id": "abc"}, "inválido"),
        ("chuva", {"since": "1980-01-01", "until": "1985-01-01", "grain": "year"}, "1991"),
    ]
    for kind, params, message in cases:
        response = client.post(
            "/api/v1/reports", json={"type": kind, "format": "pdf", "params": params}
        )
        assert response.status_code == 422, (kind, response.text)
        assert message in response.json()["detail"]
    bad_type = client.post("/api/v1/reports", json={"type": "xyz", "format": "pdf"})
    assert bad_type.status_code == 422
    assert query(select(func.count()).select_from(report_requests))[0][0] == 0


def test_ac154_expired_file_is_gone(client: TestClient) -> None:
    seed_and_compute()
    status, _ = produce(client, "risco", "csv")
    assert housekeeping(timedelta(days=8)) == (1, 0)
    expired = client.get(f"/api/v1/reports/{status['id']}").json()
    assert expired["status"] == "EXPIRED" and expired["download_url"] is None
    assert client.get(f"/api/v1/reports/{status['id']}/download").status_code == 410


def test_status_codes_and_limits(client: TestClient) -> None:
    seed_and_compute()
    first = ask(client, "risco", "csv")
    assert client.get(f"/api/v1/reports/{first['id']}/download").status_code == 409
    assert client.get(f"/api/v1/reports/{uuid.uuid4()}").status_code == 404
    for _ in range(4):
        ask(client, "risco", "csv")
    too_many = client.post("/api/v1/reports", json={"type": "risco", "format": "csv"})
    assert too_many.status_code == 429 and "em geração" in too_many.json()["detail"]
    listed = client.get(f"/api/v1/reports?ids={first['id']},nao-e-uuid").json()
    assert [r["id"] for r in listed] == [first["id"]]
    # pedido preso na fila vira falha
    assert housekeeping(timedelta(hours=1)) == (0, 5)
    assert client.get(f"/api/v1/reports/{first['id']}").json()["status"] == "FAILED"


def test_generation_failure_is_recorded(client: TestClient) -> None:
    seed_and_compute()
    run = simulate(client)
    created = ask(client, "simulacao", "pdf", {"simulation_id": run["id"]})

    async def drop_run() -> None:
        from app.models.tables import simulation_runs

        async with sessions() as factory, factory() as session:
            await session.execute(simulation_runs.delete())
            await session.commit()

    asyncio.run(drop_run())
    assert generate(created["id"]) == "FAILED"
    failed = client.get(f"/api/v1/reports/{created['id']}").json()
    assert failed["status"] == "FAILED" and "Simulação não encontrada" in failed["error"]
    assert generate(created["id"]) == "SKIPPED"  # só gera pedidos em fila

"""FR-002, FR-004, FR-005, AC-004 — comportamento da API sem serviços externos.

O lifespan só cria clientes preguiçosos (lazy): estes testes dispensam banco e Redis.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def app() -> FastAPI:
    application = create_app(get_settings())

    @application.get("/api/v1/_test/boom")
    async def boom() -> None:
        raise RuntimeError("detalhe-interno-secreto")

    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _log_records(output: str) -> list[dict[str, object]]:
    records = []
    for line in output.splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def test_liveness_returns_ok_and_version(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_not_found_is_problem_details_with_correlation_id(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = client.get("/api/v1/nope", headers={"X-Correlation-ID": "abc"})

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Correlation-ID"] == "abc"
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Recurso não encontrado"
    assert "detail" not in body  # a mensagem padrão em inglês do Starlette não é exposta
    assert body["correlation_id"] == "abc"
    assert body["instance"] == "/api/v1/nope"

    records = _log_records(capsys.readouterr().out)
    completed = [r for r in records if r.get("event") == "request_completed"]
    assert completed, "log da requisição não foi emitido"
    assert completed[-1]["correlation_id"] == "abc"
    assert completed[-1]["status"] == 404
    assert completed[-1]["service"] == "api"


def test_correlation_id_is_generated_when_absent(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert len(response.headers["X-Correlation-ID"]) == 32


def test_unhandled_error_is_500_problem_without_internal_details(client: TestClient) -> None:
    response = client.get("/api/v1/_test/boom", headers={"X-Correlation-ID": "err-1"})
    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == "err-1"
    body = response.json()
    assert body["correlation_id"] == "err-1"
    assert body["title"] == "Erro interno"
    assert "detalhe-interno-secreto" not in json.dumps(body, ensure_ascii=False)


def test_cors_allows_only_configured_origin(client: TestClient) -> None:
    allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    blocked = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in blocked.headers

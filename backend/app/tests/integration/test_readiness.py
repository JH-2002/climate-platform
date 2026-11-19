"""AC-002 / AC-003 — prontidão contra PostgreSQL/PostGIS, Redis e worker Celery reais.

Execução dentro da rede do compose:
    docker compose exec -e RUN_INTEGRATION=1 backend pytest -m integration
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.integration

if not os.environ.get("RUN_INTEGRATION"):
    pytest.skip("defina RUN_INTEGRATION=1 para rodar a integração", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(get_settings())) as test_client:
        yield test_client


def test_all_components_ready(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    body = response.json()
    assert response.status_code == 200, body
    assert body["status"] == "ok"
    for name in ("db", "postgis", "redis", "worker"):
        assert body["components"][name]["status"] == "ok"
        assert isinstance(body["components"][name]["latency_ms"], float)
    assert body["components"]["postgis"]["info"]["versão"]


def test_redis_down_returns_503_and_real_state_of_others(client: TestClient) -> None:
    resources = client.app.state.resources  # type: ignore[attr-defined]
    original = resources.redis
    # A porta 1 nunca é um Redis: simula o serviço fora do ar.
    resources.redis = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        resources.redis = original

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["components"]["redis"]["status"] == "unavailable"
    assert body["components"]["db"]["status"] == "ok"

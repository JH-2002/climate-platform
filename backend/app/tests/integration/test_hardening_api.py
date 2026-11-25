"""Spec 011 — limite de requisições com Redis real, falha aberta, cabeçalhos e 413 na API."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.rate_limit import Limits, RateLimitMiddleware, parse_networks
from app.main import create_app
from app.tests.unit.test_hardening import _call

pytestmark = [pytest.mark.integration]

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def _ok(scope: Any, receive: Any, send: Any) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _scope(ip: str, path: str = "/api/v1/reports", method: str = "POST") -> dict[str, Any]:
    return {"type": "http", "method": method, "path": path, "headers": [], "client": (ip, 1000)}


def test_ac171_heavy_limit_per_client() -> None:
    async def go() -> list[int]:
        redis = Redis.from_url(REDIS_URL)
        # janela própria do teste: o relógio aponta para um minuto que ninguém mais usa
        minute = 10_000_000 + uuid.uuid4().int % 1_000_000
        app = RateLimitMiddleware(
            _ok,
            redis_factory=lambda: redis,
            limits=Limits(general=240, heavy=3),
            trusted=parse_networks("10.0.0.0/8"),
            clock=lambda: minute * 60.0 + 30,
        )
        statuses = []
        for _ in range(4):
            status, headers, _ = await _call(app, _scope("203.0.113.50"))
            statuses.append(status)
        assert headers["retry-after"] == "30"
        other, other_headers, _ = await _call(app, _scope("203.0.113.51"))
        statuses.append(other)
        assert other_headers["ratelimit-remaining"] == "2"
        general, _, _ = await _call(app, _scope("203.0.113.50", "/api/v1/alerts/active", "GET"))
        statuses.append(general)
        await redis.aclose()
        return statuses

    assert asyncio.run(go()) == [200, 200, 200, 429, 200, 200]


def test_ac172_redis_down_fails_open() -> None:
    async def go() -> int:
        dead = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
        app = RateLimitMiddleware(_ok, lambda: dead, Limits(heavy=1), parse_networks("10.0.0.0/8"))
        statuses = [(await _call(app, _scope("203.0.113.60")))[0] for _ in range(3)]
        await dead.aclose()
        return max(statuses)

    assert asyncio.run(go()) == 200


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_HEAVY", "2")
    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_full_app_headers_429_and_413(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert "ratelimit-limit" not in health.headers  # saúde fica fora do limite
    responses = [client.get("/api/v1/analytics/describe?dataset=x") for _ in range(3)]
    assert [r.status_code == 429 for r in responses] == [False, False, True]
    limited = responses[-1]
    assert limited.headers["content-type"] == "application/problem+json"
    assert "limite é 2 por minuto" in limited.json()["detail"]
    assert limited.headers["x-frame-options"] == "DENY"
    big = client.post(
        "/api/v1/reports",
        content=b"{" + b" " * (70 * 1024) + b"}",
        headers={"content-type": "application/json"},
    )
    assert big.status_code == 413

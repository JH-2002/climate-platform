"""Spec 011 — regras do limite de requisições, IP do cliente, cabeçalhos e configuração."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.rate_limit import Limits, client_ip, client_key, parse_networks, rule_for
from app.core.security import SecurityHeadersMiddleware

TRUSTED = parse_networks("127.0.0.1/32,10.0.0.0/8,172.16.0.0/12")
LIMITS = Limits(general=240, heavy=20)


def test_rules_by_route() -> None:
    assert rule_for("GET", "/api/v1/health", LIMITS) is None
    assert rule_for("GET", "/api/v1/ready", LIMITS) is None
    assert rule_for("GET", "/", LIMITS) is None  # fora da API
    assert rule_for("GET", "/api/v1/alerts/active", LIMITS).group == "geral"  # type: ignore[union-attr]
    heavy = rule_for("POST", "/api/v1/reports", LIMITS)
    assert heavy is not None and (heavy.group, heavy.limit) == ("pesada", 20)
    assert rule_for("GET", "/api/v1/reports", LIMITS).group == "geral"  # type: ignore[union-attr]
    assert rule_for("GET", "/api/v1/analytics/series", LIMITS).group == "pesada"  # type: ignore[union-attr]
    assert rule_for("GET", "/api/v1/analytics/seriesx", LIMITS).group == "geral"  # type: ignore[union-attr]
    assert rule_for("POST", "/api/v1/simulation/runs", LIMITS).group == "pesada"  # type: ignore[union-attr]


def test_client_ip_only_trusts_known_proxies() -> None:
    # AC-173: cabeçalho vindo de quem não é proxy confiável é ignorado
    assert client_ip("203.0.113.9", "1.2.3.4", TRUSTED) == "203.0.113.9"
    # Caddy (10.0.0.5) -> Next (172.18.0.4) -> API: o cliente é o primeiro não confiável
    assert client_ip("172.18.0.4", "198.51.100.7, 10.0.0.5", TRUSTED) == "198.51.100.7"
    # quem forja um X-Forwarded-For atrás do proxy só consegue mudar o que está à esquerda
    assert client_ip("172.18.0.4", "6.6.6.6, 198.51.100.7, 10.0.0.5", TRUSTED) == "198.51.100.7"
    assert client_ip("172.18.0.4", None, TRUSTED) == "172.18.0.4"
    assert client_ip(None, None, TRUSTED) == "desconhecido"
    assert client_ip("172.18.0.4", "lixo, 10.0.0.5", TRUSTED) == "lixo"


def test_client_key_hides_the_ip() -> None:
    key = client_key("198.51.100.7")
    assert "198" not in key and len(key) == 16
    assert key == client_key("198.51.100.7") != client_key("198.51.100.8")


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "postgresql+asyncpg://climate:uma-senha-longa-e-unica@db/climate",
        "redis_url": "redis://redis:6379/0",
        "app_env": "production",
        "frontend_origin": "https://clima.exemplo.org",
    }
    base.update(overrides)
    return Settings(**base)


def test_production_rules() -> None:
    assert _settings().rate_limit_active is True
    with pytest.raises(ValidationError, match="16 caracteres"):
        _settings(database_url="postgresql+asyncpg://climate:change-me-local-only@db/climate")
    with pytest.raises(ValidationError, match="16 caracteres"):
        _settings(database_url="postgresql+asyncpg://climate:curta@db/climate")
    with pytest.raises(ValidationError, match="DEBUG"):
        _settings(log_level="DEBUG")
    with pytest.raises(ValidationError, match="https://"):
        _settings(frontend_origin="http://clima.exemplo.org")
    with pytest.raises(ValidationError):
        _settings(trusted_proxies="não é rede")
    # fora de produção, nada disso é exigido; nos testes o limite fica desligado
    dev = _settings(app_env="test", database_url="postgresql+asyncpg://c:x@db/c")
    assert dev.rate_limit_active is False
    assert _settings(app_env="test", rate_limit_enabled=True).rate_limit_active is True


async def _call(
    app: Any, scope: dict[str, Any], body: bytes = b""
) -> tuple[int, dict[str, str], bytes]:
    sent: list[dict[str, Any]] = []
    chunks = [{"type": "http.request", "body": body, "more_body": False}]

    async def receive() -> dict[str, Any]:
        return chunks.pop(0) if chunks else {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await app(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = {k.decode(): v.decode() for k, v in start["headers"]}
    payload = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], headers, payload


async def _echo(scope: Any, receive: Any, send: Any) -> None:
    message = await receive()
    body = message.get("body", b"")
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(len(body)).encode()})


def _scope(
    path: str = "/api/v1/x", headers: list[tuple[bytes, bytes]] | None = None
) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": headers or [],
        "client": ("1.2.3.4", 1),
    }


def test_security_headers_and_body_limit() -> None:
    app = SecurityHeadersMiddleware(_echo, max_body=10)
    status, headers, body = asyncio.run(_call(app, _scope(), b"12345"))
    assert (status, body) == (200, b"5")
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    # AC-174: pelo Content-Length, antes de ler
    status, headers, body = asyncio.run(_call(app, _scope(headers=[(b"content-length", b"100")])))
    assert status == 413 and json.loads(body)["status"] == 413
    assert headers["content-type"] == "application/problem+json"
    # sem Content-Length (chunked): durante a leitura
    status, _, _ = asyncio.run(_call(app, _scope(), b"x" * 11))
    assert status == 413
    _, docs_headers, _ = asyncio.run(_call(app, _scope("/api/docs"), b""))
    assert "cdn.jsdelivr.net" in docs_headers["content-security-policy"]

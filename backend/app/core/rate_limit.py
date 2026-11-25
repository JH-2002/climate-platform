"""Limite de requisições por cliente (spec 011, FR-172 e FR-173).

Janela fixa de 1 minuto no Redis: `INCR` + `EXPIRE` num pipeline (NFR-170). A regra de cada
rota e a extração do IP são funções puras. Redis fora do ar: a requisição passa (falha aberta)
e o evento vai para o log (AC-172), porque disponibilidade vale mais que o limite.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import structlog
from redis.asyncio import Redis
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.correlation import correlation_id_var
from app.core.problem import PROBLEM_MEDIA_TYPE, build_problem

logger = structlog.get_logger("app.rate_limit")

WINDOW_S = 60
EXEMPT_PATHS = frozenset({"/api/v1/health", "/api/v1/ready"})
HEAVY_RULES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/v1/simulation/runs"),
    ("POST", "/api/v1/reports"),
    ("GET", "/api/v1/geo/profile"),
    ("GET", "/api/v1/analytics/series"),
    ("GET", "/api/v1/analytics/describe"),
)


@dataclass(frozen=True)
class Limits:
    general: int = 240
    heavy: int = 20


@dataclass(frozen=True)
class Rule:
    group: str
    limit: int


def rule_for(method: str, path: str, limits: Limits) -> Rule | None:
    """Grupo e limite da rota; None = fora do limite (saúde, prontidão, fora da API)."""
    if not path.startswith("/api/") or path in EXEMPT_PATHS:
        return None
    for heavy_method, prefix in HEAVY_RULES:
        if method == heavy_method and (path == prefix or path.startswith(prefix + "/")):
            # `POST /simulation/runs/{id}/...` não existe; o prefixo cobre só a criação
            return Rule("pesada", limits.heavy)
    return Rule("geral", limits.general)


Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_networks(value: str) -> tuple[Network, ...]:
    """ "10.0.0.0/8, 172.16.0.0/12" -> redes. Valor inválido derruba a inicialização."""
    return tuple(
        ipaddress.ip_network(part.strip(), strict=False)
        for part in value.split(",")
        if part.strip()
    )


def _in(ip: str, networks: Sequence[Network]) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in networks)


def client_ip(peer: str | None, forwarded_for: str | None, trusted: Sequence[Network]) -> str:
    """IP do cliente (FR-173).

    `X-Forwarded-For` só vale quando a conexão vem de um proxy confiável; aí o cliente é o
    primeiro endereço, da direita para a esquerda, que não é proxy confiável.
    """
    peer = peer or "desconhecido"
    if not forwarded_for or not _in(peer, trusted):
        return peer
    hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
    for hop in reversed(hops):
        if not _in(hop, trusted):
            return hop
    return hops[0] if hops else peer


def client_key(ip: str) -> str:
    """Hash do IP: o endereço inteiro não vai para o Redis nem para o log (Constituição §5)."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        redis_factory: Callable[[], Redis | None],
        limits: Limits,
        trusted: Sequence[Network],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.app = app
        self.redis_factory = redis_factory
        self.limits = limits
        self.trusted = tuple(trusted)
        self.clock = clock

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rule = rule_for(scope["method"], scope["path"], self.limits)
        redis = self.redis_factory() if rule is not None else None
        if rule is None or redis is None:
            await self.app(scope, receive, send)
            return
        peer = (scope.get("client") or (None, None))[0]
        ip = client_ip(peer, Headers(scope=scope).get("x-forwarded-for"), self.trusted)
        key_hash = client_key(ip)
        now = self.clock()
        window = int(now // WINDOW_S)
        key = f"rl:{rule.group}:{key_hash}:{window}"
        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.incr(key)
                pipe.expire(key, WINDOW_S + 5)
                count, _ = await pipe.execute()
        except Exception as exc:  # falha aberta (AC-172)
            logger.warning("rate_limit_unavailable", error=type(exc).__name__)
            await self.app(scope, receive, send)
            return
        remaining = max(0, rule.limit - int(count))
        if int(count) > rule.limit:
            retry_after = max(1, int(WINDOW_S - (now % WINDOW_S)))
            logger.info("rate_limited", group=rule.group, client=key_hash, path=scope["path"])
            await self._reject(send, scope, rule, retry_after)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("RateLimit-Limit", str(rule.limit))
                headers.append("RateLimit-Remaining", str(remaining))
            await send(message)

        await self.app(scope, receive, send_with_headers)

    @staticmethod
    async def _reject(send: Send, scope: Scope, rule: Rule, retry_after: int) -> None:
        kind = (
            "pedidos pesados (simulação, relatório, perfil, séries)"
            if rule.group == "pesada"
            else "requisições"
        )
        body = json.dumps(
            build_problem(
                status=429,
                detail=f"Muitas {kind} em pouco tempo: o limite é {rule.limit} por minuto. "
                f"Tente de novo em {retry_after} s.",
                instance=scope.get("path"),
                correlation_id=correlation_id_var.get(),
            ),
            ensure_ascii=False,
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(retry_after).encode()),
                    (b"ratelimit-limit", str(rule.limit).encode()),
                    (b"ratelimit-remaining", b"0"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

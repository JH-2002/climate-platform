"""GET HTTP resiliente: timeout, retentativa com backoff exponencial + jitter (NFR-020)."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "climate-platform/0.1 (projeto de portfolio; github.com/JH-2002/climate-platform)"

Sleep = Callable[[float], Awaitable[None]]


class SourceHTTPError(RuntimeError):
    """Falha definitiva ao consultar uma fonte (após as retentativas)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class FetchResult:
    status: int
    body: bytes

    @property
    def is_empty(self) -> bool:
        return self.status == 204 or not self.body


def backoff_delay(attempt: int, base_s: float, rng: random.Random) -> float:
    """Atraso da tentativa `attempt` (1, 2, ...): base * 2^(attempt-1), com jitter de até 50%."""
    delay = base_s * 2.0 ** (attempt - 1)
    return delay * (1 + rng.random() * 0.5)


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str] | None = None,
    attempts: int = 3,
    backoff_base_s: float = 1.0,
    sleep: Sleep = asyncio.sleep,
    rng: random.Random | None = None,
) -> FetchResult:
    """Busca uma URL. Retenta erros de rede, 429 e 5xx; não retenta outros 4xx."""
    rng = rng or random.Random()  # noqa: S311 — jitter, não criptografia
    last_error = "sem tentativas"
    last_status: int | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = await client.get(url, params=params, headers={"User-Agent": USER_AGENT})
        except httpx.TransportError as exc:
            last_error = f"erro de rede: {type(exc).__name__}"
            last_status = None
        else:
            if response.status_code < 400:
                return FetchResult(response.status_code, response.content)
            last_status = response.status_code
            last_error = f"HTTP {response.status_code}"
            if response.status_code not in RETRYABLE_STATUS:
                break
        if attempt < attempts:
            await sleep(backoff_delay(attempt, backoff_base_s, rng))
    raise SourceHTTPError(last_error, status=last_status)

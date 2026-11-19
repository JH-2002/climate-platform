"""Avaliação de prontidão (readiness) — FR-003, BR-001.

Orquestração pura: recebe funções assíncronas de verificação, executa todas em paralelo
com timeout e agrega o resultado. Sem cache: cada chamada faz verificações reais.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

ComponentStatus = Literal["ok", "unavailable"]
OverallStatus = Literal["ok", "degraded"]

# Uma verificação lança exceção se falhar; pode retornar dados extras (ex.: versão).
CheckFn = Callable[[], Awaitable[Mapping[str, str] | None]]


class ComponentResult(BaseModel):
    status: ComponentStatus
    latency_ms: float | None = Field(default=None, description="Duração medida da verificação")
    detail: str | None = None
    info: dict[str, str] = Field(default_factory=dict)


class ReadinessReport(BaseModel):
    status: OverallStatus
    checked_at: datetime
    components: dict[str, ComponentResult]


class LivenessReport(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


def _describe_failure(exc: BaseException) -> str:
    # Apenas a classe da exceção: a mensagem pode conter hosts ou credenciais.
    return f"falha na verificação: {type(exc).__name__}"


async def run_check(check: CheckFn, timeout_s: float) -> ComponentResult:
    start = time.perf_counter()
    try:
        info = await asyncio.wait_for(check(), timeout=timeout_s)
    except TimeoutError:
        return ComponentResult(status="unavailable", detail=f"sem resposta em {timeout_s:g} s")
    except Exception as exc:
        return ComponentResult(
            status="unavailable",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            detail=_describe_failure(exc),
        )
    return ComponentResult(
        status="ok",
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
        info=dict(info or {}),
    )


async def run_readiness(
    checks: Mapping[str, CheckFn],
    timeout_s: float,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ReadinessReport:
    names = list(checks)
    results = await asyncio.gather(*(run_check(checks[name], timeout_s) for name in names))
    components = dict(zip(names, results, strict=True))
    overall: OverallStatus = (
        "ok" if components and all(r.status == "ok" for r in components.values()) else "degraded"
    )
    return ReadinessReport(status=overall, checked_at=now(), components=components)

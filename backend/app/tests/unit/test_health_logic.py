"""FR-003 / BR-001 — agregação da verificação de prontidão."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from app.core.health import run_check, run_readiness

FIXED_NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)


async def _ok() -> None:
    return None


async def _ok_with_info() -> dict[str, str]:
    return {"versão": "3.4.3"}


async def _boom() -> None:
    raise ConnectionRefusedError("postgresql://user:secret@db:5432 refused")


async def _slow() -> None:
    await asyncio.sleep(5)


def test_all_components_ok_gives_ok_status() -> None:
    report = asyncio.run(
        run_readiness({"db": _ok, "postgis": _ok_with_info}, timeout_s=1, now=lambda: FIXED_NOW)
    )
    assert report.status == "ok"
    assert report.checked_at == FIXED_NOW
    assert report.components["postgis"].info == {"versão": "3.4.3"}
    assert report.components["db"].latency_ms is not None


def test_one_failure_degrades_and_keeps_other_components_real() -> None:
    report = asyncio.run(run_readiness({"db": _ok, "redis": _boom}, timeout_s=1))
    assert report.status == "degraded"
    assert report.components["db"].status == "ok"
    assert report.components["redis"].status == "unavailable"


def test_failure_detail_does_not_leak_exception_message() -> None:
    result = asyncio.run(run_check(_boom, timeout_s=1))
    assert result.detail == "falha na verificação: ConnectionRefusedError"
    assert "secret" not in (result.detail or "")


def test_timeout_is_reported_as_unavailable() -> None:
    result = asyncio.run(run_check(_slow, timeout_s=0.05))
    assert result.status == "unavailable"
    assert result.detail == "sem resposta em 0.05 s"


def test_checks_run_concurrently() -> None:
    async def sleepy() -> None:
        await asyncio.sleep(0.2)

    start = time.perf_counter()
    asyncio.run(run_readiness({"a": sleepy, "b": sleepy, "c": sleepy}, timeout_s=1))
    assert time.perf_counter() - start < 0.5


def test_no_checks_is_not_ok() -> None:
    report = asyncio.run(run_readiness({}, timeout_s=1))
    assert report.status == "degraded"


def test_each_call_performs_the_check_again() -> None:
    calls = 0

    async def counting() -> None:
        nonlocal calls
        calls += 1

    asyncio.run(run_readiness({"x": counting}, timeout_s=1))
    asyncio.run(run_readiness({"x": counting}, timeout_s=1))
    assert calls == 2

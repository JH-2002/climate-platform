"""NFR-020 / AC-023 — regras puras do pipeline (circuit breaker, status final, erros)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("sqlalchemy")

from app.ingestion.pipeline import (
    JobResult,
    circuit_is_open,
    final_status,
    summarize_error,
)

NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)


def _runs(statuses: list[str], newest_minutes_ago: int = 1) -> list[tuple[str, datetime]]:
    return [(s, NOW - timedelta(minutes=newest_minutes_ago + i)) for i, s in enumerate(statuses)]


def test_circuit_opens_after_five_recent_failures() -> None:
    assert circuit_is_open(_runs(["FAILED"] * 5), NOW)


def test_circuit_stays_closed_with_fewer_failures_or_a_success() -> None:
    assert not circuit_is_open(_runs(["FAILED"] * 4), NOW)
    assert not circuit_is_open(_runs(["FAILED", "FAILED", "SUCCESS", "FAILED", "FAILED"]), NOW)


def test_circuit_closes_after_cooldown() -> None:
    assert not circuit_is_open(_runs(["FAILED"] * 5, newest_minutes_ago=11), NOW)


def test_final_status() -> None:
    assert final_status(JobResult(received=2, inserted=2)) == "SUCCESS"
    assert final_status(JobResult(received=3, inserted=2, rejected=1)) == "PARTIAL"
    assert final_status(JobResult(received=2, rejected=2)) == "FAILED"
    assert final_status(JobResult()) == "SUCCESS"


def test_error_summary_hides_credentials_and_is_bounded() -> None:
    exc = RuntimeError("falha em postgresql+asyncpg://u:segredo@db/x " + "x" * 1000)
    summary = summarize_error(exc)
    assert "segredo" not in summary
    assert summary.startswith("RuntimeError: ")
    assert len(summary) <= 500

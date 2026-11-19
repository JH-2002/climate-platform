"""Frescor do heartbeat do agendador usado no healthcheck do container."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.workers.healthcheck import heartbeat_is_fresh, main

NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)


def test_recent_heartbeat_is_fresh() -> None:
    raw = (NOW - timedelta(seconds=30)).isoformat().encode()
    assert heartbeat_is_fresh(raw, NOW, max_age_s=120)


def test_old_heartbeat_is_stale() -> None:
    raw = (NOW - timedelta(minutes=5)).isoformat()
    assert not heartbeat_is_fresh(raw, NOW, max_age_s=120)


def test_missing_or_garbage_heartbeat_is_not_fresh() -> None:
    assert not heartbeat_is_fresh(None, NOW, 120)
    assert not heartbeat_is_fresh(b"not-a-date", NOW, 120)
    assert not heartbeat_is_fresh("2026-11-19T15:00:00", NOW, 120)  # data sem fuso é rejeitada


def test_future_heartbeat_is_not_fresh() -> None:
    assert not heartbeat_is_fresh((NOW + timedelta(minutes=1)).isoformat(), NOW, 120)


def test_unknown_target_returns_usage_error() -> None:
    assert main(["healthcheck", "nope"]) == 2

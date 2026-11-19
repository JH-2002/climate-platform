"""BR-020 — classificação de frescor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.freshness import classify_freshness

NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)
HOUR = 3600


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(minutes=30), ("FRESH", "ok")),
        (timedelta(minutes=90), ("FRESH", "ok")),
        (timedelta(minutes=91), ("DELAYED", "delayed")),
        (timedelta(hours=3), ("DELAYED", "delayed")),
        (timedelta(hours=3, seconds=1), ("STALE", "stale")),
    ],
)
def test_age_thresholds(age: timedelta, expected: tuple[str, str]) -> None:
    result = classify_freshness(
        now=NOW, last_success_at=NOW - age, expected_interval_s=HOUR, last_run_status="SUCCESS"
    )
    assert (result.freshness, result.reason) == expected


def test_missing_credentials_wins() -> None:
    result = classify_freshness(
        now=NOW,
        last_success_at=NOW,
        expected_interval_s=HOUR,
        last_run_status="SUCCESS",
        credentials_missing=True,
    )
    assert (result.freshness, result.reason) == ("UNAVAILABLE", "missing_credentials")


def test_last_failure_is_unavailable_even_with_recent_success() -> None:
    result = classify_freshness(
        now=NOW, last_success_at=NOW, expected_interval_s=HOUR, last_run_status="FAILED"
    )
    assert (result.freshness, result.reason) == ("UNAVAILABLE", "last_run_failed")


def test_never_collected_is_unknown() -> None:
    result = classify_freshness(
        now=NOW, last_success_at=None, expected_interval_s=HOUR, last_run_status=None
    )
    assert (result.freshness, result.reason) == ("UNKNOWN", "never_collected")


def test_disabled_source_is_unavailable() -> None:
    result = classify_freshness(
        now=NOW, last_success_at=NOW, expected_interval_s=HOUR, last_run_status=None, enabled=False
    )
    assert (result.freshness, result.reason) == ("UNAVAILABLE", "disabled")

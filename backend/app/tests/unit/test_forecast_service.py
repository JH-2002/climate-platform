"""T030 — regras puras do painel: hora corrente, pivot e acumulados previstos (BR-040 a BR-042)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("geoalchemy2")

from app.services.forecast import (
    current_hour,
    local_midnight_utc,
    pivot_daily,
    pivot_hourly,
    precipitation_outlook,
)

T0 = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)


def test_current_hour_floors_to_utc_hour() -> None:
    assert current_hour(datetime(2026, 11, 19, 15, 47, 12, tzinfo=UTC)) == T0


def test_local_midnight_is_brasilia_day_start_in_utc() -> None:
    assert local_midnight_utc(datetime(2026, 11, 19, 1, 0, tzinfo=UTC)) == datetime(
        2026, 11, 18, 3, 0, tzinfo=UTC
    )
    assert local_midnight_utc(T0) == datetime(2026, 11, 19, 3, 0, tzinfo=UTC)


def test_pivot_hourly_groups_variables_by_time() -> None:
    rows = [
        (T0, "air_temperature", 25.0),
        (T0, "precipitation", 0.4),
        (T0 + timedelta(hours=1), "air_temperature", 24.0),
        (T0, "unknown_variable", 1.0),
    ]
    result = pivot_hourly(rows)
    assert [r.valid_at for r in result] == [T0, T0 + timedelta(hours=1)]
    assert result[0].air_temperature == 25.0
    assert result[0].precipitation == 0.4
    assert result[1].precipitation is None


def test_pivot_daily_uses_local_date() -> None:
    local_midnight = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
    result = pivot_daily([(local_midnight, "precipitation_sum", 6.5)])
    assert result[0].date == date(2026, 11, 20)
    assert result[0].precipitation_sum == 6.5


def test_outlook_complete() -> None:
    precip = {T0 + timedelta(hours=h): 0.5 for h in range(3)}
    result = precipitation_outlook(precip, T0, 3)
    assert (result.total_mm, result.complete, result.hours_available) == (1.5, True, 3)


def test_outlook_with_missing_hour_is_incomplete() -> None:
    precip = {T0: 1.0, T0 + timedelta(hours=2): 2.0}
    result = precipitation_outlook(precip, T0, 3)
    assert (result.total_mm, result.complete, result.hours_available) == (3.0, False, 2)

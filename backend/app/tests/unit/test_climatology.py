"""T075 — climatologia, anomalias e sequências secas (BR-081)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.analytics.climatology import (
    annual_normal,
    annual_totals,
    current_dry_spell,
    daily_percentile_for_month,
    max_dry_spells_by_year,
    month_to_date,
    monthly_normals,
    monthly_totals,
    moving_average,
)


def daily_series(start: date, end: date, value: float = 2.0) -> dict[date, float]:
    days: dict[date, float] = {}
    d = start
    while d <= end:
        days[d] = value
        d += timedelta(days=1)
    return days


def test_monthly_normals_require_25_years() -> None:
    monthly = {(y, m): float(m) for y in range(1991, 2021) for m in range(1, 13)}
    normals = monthly_normals(monthly)
    assert normals[3].mean == 3.0 and normals[3].years_used == 30
    assert annual_normal(normals) == pytest.approx(78.0)
    for y in range(1991, 1997):  # 6 anos sem janeiro → 24 anos: insuficiente
        del monthly[(y, 1)]
    normals = monthly_normals(monthly)
    assert 1 not in normals
    assert annual_normal(normals) is None


def test_monthly_and_annual_totals_skip_incomplete_periods() -> None:
    daily = daily_series(date(2020, 1, 1), date(2020, 3, 15))
    totals = monthly_totals(daily)
    assert totals == {(2020, 1): 62.0, (2020, 2): 58.0}  # 2020 é bissexto; março incompleto
    assert annual_totals(totals) == {}


def test_moving_average_needs_consecutive_years() -> None:
    series = [(y, float(y - 2000)) for y in range(2000, 2012)]
    result = moving_average(series, window=10)
    assert result == [(2009, 4.5), (2010, 5.5), (2011, 6.5)]
    gap = [(y, 1.0) for y in (2000, 2001, 2003)]
    assert moving_average(gap, window=3) == []


def test_daily_percentile_for_month() -> None:
    daily: dict[date, float] = {}
    for year in range(1991, 2021):
        for day in range(1, 31):
            daily[date(year, 11, day)] = float(day)  # 1..30 mm em todo novembro
    # 900 valores (1..30, 30 vezes cada): posição 854,05 → valor 29
    assert daily_percentile_for_month(daily, 11, 95) == pytest.approx(29.0)
    assert daily_percentile_for_month(daily, 12, 95) is None  # sem dezembro


def test_month_to_date_compares_same_day_range() -> None:
    daily: dict[date, float] = {}
    for year in range(1991, 2021):
        for day in range(1, 31):
            daily[date(year, 11, day)] = 2.0
    for day in range(1, 19):
        daily[date(2026, 11, day)] = 5.0
    comparison = month_to_date(daily, date(2026, 11, 18))
    assert comparison is not None
    assert (comparison.current, comparison.reference) == (90.0, 36.0)
    assert comparison.ratio == pytest.approx(2.5)
    assert (comparison.days, comparison.years_used) == (18, 30)
    del daily[date(2026, 11, 3)]
    assert month_to_date(daily, date(2026, 11, 18)) is None  # mês atual com falha


def test_dry_spells() -> None:
    daily = daily_series(date(2026, 11, 1), date(2026, 11, 18), 0.0)
    daily[date(2026, 11, 10)] = 12.0
    assert current_dry_spell(daily, date(2026, 11, 18)) == 8
    assert current_dry_spell(daily, date(2026, 11, 10)) == 0
    history: dict[date, float] = {}
    for year in range(1991, 1994):
        for day in range(1, 31):
            history[date(year, 11, day)] = 0.0 if day <= year - 1985 else 3.0
    assert max_dry_spells_by_year(history, 11, 1991, 1993) == [6, 7, 8]

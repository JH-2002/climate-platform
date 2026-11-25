"""Climatologia, anomalias e sequências secas (BR-081, BR-083). Funções puras.

Convenções:
- `daily`: dia -> valor (mm ou °C), só dias presentes.
- `monthly`: (ano, mês) -> total mensal.
- Normal exige ao menos `MIN_YEARS` anos com dado no período (BR-081).
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.analytics.stats import percentile

NORMAL_START, NORMAL_END = 1991, 2020
MIN_YEARS = 25
DRY_DAY_MM = 1.0


@dataclass(frozen=True)
class MonthlyNormal:
    month: int
    mean: float
    years_used: int


def monthly_normals(
    monthly: Mapping[tuple[int, int], float],
    start_year: int = NORMAL_START,
    end_year: int = NORMAL_END,
    min_years: int = MIN_YEARS,
) -> dict[int, MonthlyNormal]:
    """Média de cada mês no período; mês com menos de `min_years` anos fica de fora."""
    result: dict[int, MonthlyNormal] = {}
    for month in range(1, 13):
        values = [
            monthly[(y, month)] for y in range(start_year, end_year + 1) if (y, month) in monthly
        ]
        if len(values) >= min_years:
            result[month] = MonthlyNormal(month, sum(values) / len(values), len(values))
    return result


def annual_normal(normals: Mapping[int, MonthlyNormal]) -> float | None:
    if len(normals) < 12:
        return None
    return sum(n.mean for n in normals.values())


def monthly_totals(daily: Mapping[date, float]) -> dict[tuple[int, int], float]:
    """Totais mensais de meses completos (mês com dia faltando não entra)."""
    sums: dict[tuple[int, int], float] = defaultdict(float)
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for day, value in daily.items():
        sums[(day.year, day.month)] += value
        counts[(day.year, day.month)] += 1
    return {key: sums[key] for key in sums if counts[key] == calendar.monthrange(key[0], key[1])[1]}


def annual_totals(monthly: Mapping[tuple[int, int], float]) -> dict[int, float]:
    by_year: dict[int, list[float]] = defaultdict(list)
    for (year, _month), value in monthly.items():
        by_year[year].append(value)
    return {year: sum(values) for year, values in sorted(by_year.items()) if len(values) == 12}


def moving_average(
    series: Sequence[tuple[int, float]], window: int = 10
) -> list[tuple[int, float]]:
    """Média móvel retroativa: o ponto de um ano usa ele e os `window − 1` anteriores."""
    ordered = sorted(series)
    result: list[tuple[int, float]] = []
    for i in range(window - 1, len(ordered)):
        chunk = ordered[i - window + 1 : i + 1]
        if chunk[-1][0] - chunk[0][0] == window - 1:  # anos consecutivos
            result.append((ordered[i][0], sum(v for _, v in chunk) / window))
    return result


def daily_values_in_month(
    daily: Mapping[date, float], month: int, start_year: int, end_year: int
) -> list[float]:
    return [v for d, v in daily.items() if d.month == month and start_year <= d.year <= end_year]


def daily_percentile_for_month(
    daily: Mapping[date, float],
    month: int,
    q: float,
    start_year: int = NORMAL_START,
    end_year: int = NORMAL_END,
    min_years: int = MIN_YEARS,
) -> float | None:
    """Percentil das chuvas diárias (todos os dias) de um mês no período de referência."""
    years = {d.year for d in daily if d.month == month and start_year <= d.year <= end_year}
    if len(years) < min_years:
        return None
    return percentile(sorted(daily_values_in_month(daily, month, start_year, end_year)), q)


@dataclass(frozen=True)
class PeriodComparison:
    current: float
    reference: float  # média do mesmo intervalo de dias nos anos de referência
    ratio: float | None  # current / reference
    days: int
    years_used: int


def month_to_date(
    daily: Mapping[date, float],
    until: date,
    start_year: int = NORMAL_START,
    end_year: int = NORMAL_END,
    min_years: int = MIN_YEARS,
) -> PeriodComparison | None:
    """Acumulado do dia 1 até `until` frente à média do mesmo intervalo nos anos de referência."""
    days = until.day
    current_days = [date(until.year, until.month, d) for d in range(1, days + 1)]
    if any(d not in daily for d in current_days):
        return None
    current = sum(daily[d] for d in current_days)
    totals: list[float] = []
    for year in range(start_year, end_year + 1):
        span = [
            date(year, until.month, d) for d in range(1, min(days, _days_in(year, until.month)) + 1)
        ]
        if all(d in daily for d in span):
            totals.append(sum(daily[d] for d in span))
    if len(totals) < min_years:
        return None
    reference = sum(totals) / len(totals)
    return PeriodComparison(
        current=current,
        reference=reference,
        ratio=current / reference if reference > 0 else None,
        days=days,
        years_used=len(totals),
    )


def _days_in(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def current_dry_spell(daily: Mapping[date, float], until: date, dry_mm: float = DRY_DAY_MM) -> int:
    """Dias seguidos com chuva < `dry_mm` terminando em `until` (para no primeiro dia ausente)."""
    count = 0
    day = until
    while day in daily and daily[day] < dry_mm:
        count += 1
        day -= timedelta(days=1)
    return count


def max_dry_spells_by_year(
    daily: Mapping[date, float],
    month: int,
    start_year: int = NORMAL_START,
    end_year: int = NORMAL_END,
    dry_mm: float = DRY_DAY_MM,
) -> list[int]:
    """Maior sequência seca dentro do mês, para cada ano completo do período."""
    spells: list[int] = []
    for year in range(start_year, end_year + 1):
        days = [date(year, month, d) for d in range(1, _days_in(year, month) + 1)]
        if not all(d in daily for d in days):
            continue
        best = run = 0
        for d in days:
            run = run + 1 if daily[d] < dry_mm else 0
            best = max(best, run)
        spells.append(best)
    return spells

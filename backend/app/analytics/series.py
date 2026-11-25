"""Séries agregadas: períodos, cobertura (BR-084), deslocamentos e histograma. Puras."""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
from typing import Literal

Grain = Literal["hour", "day", "week", "month", "year"]
Resolution = Literal["hour", "day", "month"]
CompareMode = Literal["normal", "previous_period", "same_period_last_year"]

PARTIAL_BELOW = 0.8
INSUFFICIENT_BELOW = 0.5


def bucket_start(d: date, grain: Grain) -> date:
    if grain in ("hour", "day"):
        return d
    if grain == "week":
        return d - timedelta(days=d.weekday())  # segunda-feira (ISO)
    if grain == "month":
        return d.replace(day=1)
    return d.replace(month=1, day=1)


def bucket_end(start: date, grain: Grain) -> date:
    """Primeiro dia depois do período (exclusivo)."""
    if grain in ("hour", "day"):
        return start + timedelta(days=1)
    if grain == "week":
        return start + timedelta(days=7)
    if grain == "month":
        days = calendar.monthrange(start.year, start.month)[1]
        return start + timedelta(days=days)
    return date(start.year + 1, 1, 1)


def buckets(start: date, end: date, grain: Grain) -> list[date]:
    """Inícios dos períodos que tocam [start, end] (dias inclusivos)."""
    result: list[date] = []
    current = bucket_start(start, grain)
    while current <= end:
        result.append(current)
        current = bucket_end(current, grain)
    return result


def expected_count(
    bucket: date, grain: Grain, resolution: Resolution, clip_start: date, clip_end: date
) -> int:
    """Quantos valores deveriam existir no período, dentro do intervalo pedido."""
    first = max(bucket, clip_start)
    last = min(bucket_end(bucket, grain) - timedelta(days=1), clip_end)
    if last < first:
        return 0
    days = (last - first).days + 1
    if resolution == "day":
        return days
    if resolution == "hour":
        return days * 24
    months = (last.year - first.year) * 12 + last.month - first.month + 1
    return months


@dataclass(frozen=True)
class Finalized:
    value: float | None
    coverage: float
    partial: bool
    insufficient: bool


def finalize(value: float | None, present: int, expected: int) -> Finalized:
    """BR-084: < 80% de cobertura é parcial; < 50% não exibe o valor."""
    coverage = min(1.0, present / expected) if expected > 0 else 0.0
    insufficient = coverage < INSUFFICIENT_BELOW
    return Finalized(
        value=None if insufficient else value,
        coverage=round(coverage, 4),
        partial=not insufficient and coverage < PARTIAL_BELOW,
        insufficient=insufficient,
    )


def shifted_window(start: date, end: date, mode: CompareMode) -> tuple[date, date]:
    """Janela de comparação: período imediatamente anterior ou mesmo período do ano anterior."""
    if mode == "previous_period":
        span = end - start
        return start - span - timedelta(days=1), start - timedelta(days=1)
    if mode == "same_period_last_year":
        return _minus_year(start), _minus_year(end)
    raise ValueError("a comparação com a normal não usa janela deslocada")


def _minus_year(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29/02
        return d.replace(year=d.year - 1, day=28)


def histogram(values: Sequence[float], edges: Sequence[float]) -> list[int]:
    """Contagem por faixa [edges[i], edges[i+1]); a última faixa inclui o limite superior."""
    if len(edges) < 2 or any(b <= a for a, b in pairwise(edges)):
        raise ValueError("limites das faixas devem ser crescentes")
    counts = [0] * (len(edges) - 1)
    for v in values:
        if v < edges[0] or v > edges[-1]:
            continue
        for i in range(len(counts)):
            last = i == len(counts) - 1
            if edges[i] <= v < edges[i + 1] or (last and v == edges[-1]):
                counts[i] += 1
                break
    return counts

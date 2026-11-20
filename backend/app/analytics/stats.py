"""Estatísticas descritivas (FR-083). Funções puras, sem dependências externas."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

IQR_FACTOR = 1.5
MAX_LISTED_OUTLIERS = 10


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Percentil com interpolação linear (método 7 de Hyndman & Fan, padrão do NumPy)."""
    if not sorted_values:
        raise ValueError("série vazia")
    if not 0 <= q <= 100:
        raise ValueError("percentil fora de 0–100")
    position = (len(sorted_values) - 1) * q / 100
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(sorted_values[low])
    weight = position - low
    return float(sorted_values[low] * (1 - weight) + sorted_values[high] * weight)


@dataclass(frozen=True)
class Description:
    n: int
    missing: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    std: float | None  # amostral (n − 1)
    p5: float | None
    p25: float | None
    p75: float | None
    p95: float | None
    outlier_count: int
    outliers: tuple[float, ...]  # os mais distantes da mediana, até MAX_LISTED_OUTLIERS

    @property
    def coverage(self) -> float:
        total = self.n + self.missing
        return self.n / total if total else 0.0


def describe(values: Sequence[float | None]) -> Description:
    present = sorted(float(v) for v in values if v is not None and math.isfinite(v))
    missing = len(values) - len(present)
    n = len(present)
    if n == 0:
        return Description(0, missing, None, None, None, None, None, None, None, None, None, 0, ())
    mean = sum(present) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in present) / (n - 1)) if n > 1 else None
    p25, p75 = percentile(present, 25), percentile(present, 75)
    median = percentile(present, 50)
    iqr = p75 - p25
    low, high = p25 - IQR_FACTOR * iqr, p75 + IQR_FACTOR * iqr
    outliers = [v for v in present if v < low or v > high]
    listed = sorted(outliers, key=lambda v: abs(v - median), reverse=True)[:MAX_LISTED_OUTLIERS]
    return Description(
        n=n,
        missing=missing,
        mean=mean,
        median=median,
        minimum=present[0],
        maximum=present[-1],
        std=std,
        p5=percentile(present, 5),
        p25=p25,
        p75=p75,
        p95=percentile(present, 95),
        outlier_count=len(outliers),
        outliers=tuple(listed),
    )


def coverage(present: int, expected: int) -> float:
    """Proporção de valores presentes num intervalo (BR-084)."""
    if expected <= 0:
        return 0.0
    return min(1.0, present / expected)

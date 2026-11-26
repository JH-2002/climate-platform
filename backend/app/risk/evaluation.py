"""Avaliação retrospectiva do motor (spec 015, FR-211 a FR-214). Funções puras.

Unidade: subprefeitura × dia local. Previsão positiva: algum setor da subprefeitura em alto ou
crítico. Observação positiva: ao menos uma ocorrência registrada na subprefeitura naquele dia.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta

from app.risk.coefficients import Category, Coefficients

ORDER = {Category.LOW: 0, Category.MODERATE: 1, Category.HIGH: 2, Category.CRITICAL: 3}
POSITIVE = frozenset({Category.HIGH, Category.CRITICAL})
CALIBRATION_FACTORS: tuple[float, ...] = tuple(round(0.3 + 0.1 * i, 1) for i in range(13))


def normalize_name(name: str | None) -> str:
    """Nome de subprefeitura comparável: sem acento, maiúsculo, espaços simples."""
    if not name:
        return ""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    for sep in ("-", "/", "'"):
        plain = plain.replace(sep, " ")
    return " ".join(plain.split())


@dataclass(frozen=True)
class Contingency:
    hits: int = 0
    misses: int = 0
    false_alarms: int = 0
    correct_negatives: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses + self.false_alarms + self.correct_negatives

    @property
    def events(self) -> int:
        return self.hits + self.misses

    @property
    def pod(self) -> float | None:
        """Taxa de detecção: dos dias com ocorrência, quantos foram marcados."""
        return _ratio(self.hits, self.hits + self.misses)

    @property
    def far(self) -> float | None:
        """Razão de alarmes falsos: dos dias marcados, quantos ficaram sem ocorrência registrada."""
        return _ratio(self.false_alarms, self.hits + self.false_alarms)

    @property
    def csi(self) -> float | None:
        """Índice de sucesso crítico: acertos sobre acertos, falhas e alarmes falsos."""
        return _ratio(self.hits, self.hits + self.misses + self.false_alarms)

    @property
    def bias(self) -> float | None:
        """Viés de frequência: dias marcados sobre dias com ocorrência (1 = mesma frequência)."""
        return _ratio(self.hits + self.false_alarms, self.hits + self.misses)

    @property
    def base_rate(self) -> float | None:
        return _ratio(self.events, self.total)

    def add(self, predicted: bool, observed: bool) -> Contingency:
        if predicted and observed:
            return replace(self, hits=self.hits + 1)
        if observed:
            return replace(self, misses=self.misses + 1)
        if predicted:
            return replace(self, false_alarms=self.false_alarms + 1)
        return replace(self, correct_negatives=self.correct_negatives + 1)

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "false_alarms": self.false_alarms,
            "correct_negatives": self.correct_negatives,
            "units": self.total,
            "events": self.events,
            "pod": _round(self.pod),
            "far": _round(self.far),
            "csi": _round(self.csi),
            "bias": _round(self.bias),
            "base_rate": _round(self.base_rate),
        }


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


@dataclass(frozen=True)
class DayUnit:
    day: date
    subprefecture: str
    max_category: Category
    observed: bool

    @property
    def predicted(self) -> bool:
        return self.max_category in POSITIVE


def day_units(
    day: date,
    categories: Mapping[int, Category],
    sector_subprefecture: Mapping[int, str],
    occurrences: set[tuple[date, str]],
) -> list[DayUnit]:
    """Maior categoria de cada subprefeitura no dia; sem categoria conhecida, fica de fora."""
    best: dict[str, Category] = {}
    for sector_id, cat in categories.items():
        sub = sector_subprefecture.get(sector_id)
        if not sub or cat not in ORDER:
            continue
        if sub not in best or ORDER[cat] > ORDER[best[sub]]:
            best[sub] = cat
    return [DayUnit(day, sub, cat, (day, sub) in occurrences) for sub, cat in sorted(best.items())]


def contingency(units: Iterable[DayUnit]) -> Contingency:
    table = Contingency()
    for u in units:
        table = table.add(u.predicted, u.observed)
    return table


def reliability(units: Sequence[DayUnit]) -> list[dict[str, object]]:
    """Para cada categoria máxima do dia-subprefeitura, quantos tiveram ocorrência."""
    counts: dict[Category, list[int]] = {cat: [0, 0] for cat in ORDER}
    for u in units:
        counts[u.max_category][0] += 1
        counts[u.max_category][1] += int(u.observed)
    return [
        {
            "category": cat.value,
            "units": n,
            "with_occurrence": hit,
            "rate": _round(_ratio(hit, n)),
        }
        for cat, (n, hit) in counts.items()
    ]


def by_month(units: Sequence[DayUnit]) -> list[dict[str, object]]:
    months: dict[str, Contingency] = defaultdict(Contingency)
    for u in units:
        key = u.day.strftime("%Y-%m")
        months[key] = months[key].add(u.predicted, u.observed)
    return [{"month": m, **table.as_dict()} for m, table in sorted(months.items())]


def nearby_counts(
    occurrence_days: Mapping[int, Sequence[date]], day: date, window_days: int
) -> dict[int, int]:
    """Ocorrências perto de cada setor na janela que termina na véspera de `day` (sem vazamento)."""
    since, until = day - timedelta(days=window_days), day - timedelta(days=1)
    return {
        sector: sum(1 for d in days if since <= d <= until)
        for sector, days in occurrence_days.items()
    }


def _scale(values: tuple[float, float, float], factor: float) -> tuple[float, float, float]:
    low, mid, high = values
    return (round(low * factor, 2), round(mid * factor, 2), round(high * factor, 2))


def scaled(c: Coefficients, factor: float) -> Coefficients:
    """Mesmos coeficientes com as faixas de chuva de 1 h e 24 h multiplicadas por `factor`."""
    return replace(
        c,
        p1h_thresholds_mm=_scale(c.p1h_thresholds_mm, factor),
        p24_thresholds_mm=_scale(c.p24_thresholds_mm, factor),
    )


def best_factor(scores: Sequence[tuple[float, float | None]]) -> float | None:
    """Fator de maior CSI entre pares (fator, CSI); empate fica com o mais perto de 1,0."""
    ranked = [(csi, -abs(factor - 1.0), factor) for factor, csi in scores if csi is not None]
    return max(ranked)[2] if ranked else None

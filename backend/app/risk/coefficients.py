"""Coeficientes do motor v0 — todos **experimentais** (Constituição §13, spec 005 BR-060 a BR-064).

Qualquer mudança de valor exige nova `ENGINE_VERSION` e registro em specs/005 ou ADR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

ENGINE_VERSION = "0.1.0-experimental"


class Category(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


_L, _M, _H, _C = Category.LOW, Category.MODERATE, Category.HIGH, Category.CRITICAL

# BR-062 — linhas: nível de chuva 0..3; colunas: suscetibilidade 1..4.
RISK_MATRIX: dict[int, tuple[Category, Category, Category, Category]] = {
    0: (_L, _L, _L, _L),
    1: (_L, _L, _M, _M),
    2: (_L, _M, _H, _H),
    3: (_M, _H, _C, _C),
}


@dataclass(frozen=True)
class Coefficients:
    # BR-060. Origem: classificação usual de intensidade de chuva (moderada até ~10 mm/h,
    # forte acima, muito forte a partir de ~50 mm/h). Limites de 24 h provisórios.
    p1h_thresholds_mm: tuple[float, float, float] = (10.0, 25.0, 50.0)
    p24_thresholds_mm: tuple[float, float, float] = (30.0, 60.0, 100.0)
    antecedent_threshold_mm: float = 50.0
    antecedent_hours: int = 72
    window_hours: int = 24
    max_missing_hours: int = 2
    # BR-061
    occurrence_radius_m: float = 300.0
    occurrence_window_days: int = 365
    occurrence_min_count: int = 2
    flood_extent_return_period_years: int = 100
    # BR-063 e BR-064
    max_point_distance_km: float = 25.0
    validity_hours: int = 24
    stale_after_hours: int = 3

    def as_params(self) -> dict[str, Any]:
        params = asdict(self)
        params["engine_version"] = ENGINE_VERSION
        params["status"] = "experimental"
        return params


DEFAULT_COEFFICIENTS = Coefficients()

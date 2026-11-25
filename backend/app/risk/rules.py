"""Regras do motor v0 (BR-060 a BR-063) e textos explicativos em português."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.risk.coefficients import RISK_MATRIX, Category, Coefficients

Effect = Literal["raises", "info", "unknown"]

RAIN_LEVEL_NAMES = {1: "moderada", 2: "forte", 3: "muito forte"}
UNKNOWN_FRESHNESS = frozenset({"STALE", "UNAVAILABLE", "UNKNOWN"})


@dataclass(frozen=True)
class Factor:
    code: str
    text: str
    effect: Effect

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "text": self.text, "effect": self.effect}


def format_mm(value: float) -> str:
    """12.5 -> "12,5"; 30.0 -> "30" (formato brasileiro, sem casas desnecessárias)."""
    rounded = round(value, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}".replace(".", ",")


def level_for(value: float | None, thresholds: Sequence[float]) -> int:
    """Quantos limites o valor atinge (0 = abaixo do primeiro)."""
    if value is None:
        return 0
    return sum(1 for limit in thresholds if value >= limit)


def rain_level(p1h_max: float | None, p24: float | None, a72: float | None, c: Coefficients) -> int:
    """BR-060: maior nível entre P1h e P24; +1 com A72 alto se já houver gatilho (teto 3).

    Solo encharcado sem chuva prevista não cria gatilho: o bônus só vale com nível >= 1.
    """
    base = max(level_for(p1h_max, c.p1h_thresholds_mm), level_for(p24, c.p24_thresholds_mm))
    if base >= 1 and a72 is not None and a72 >= c.antecedent_threshold_mm:
        return min(3, base + 1)
    return base


def susceptibility(
    grade: int, in_flood_extent: bool, nearby_occurrences: int, c: Coefficients
) -> int:
    """BR-061: grau oficial (1–4), +1 se cruza mancha ou tem ocorrências próximas (teto 4)."""
    if not 1 <= grade <= 4:
        raise ValueError(f"grau fora de 1–4: {grade}")
    bonus = in_flood_extent or nearby_occurrences >= c.occurrence_min_count
    return min(4, grade + (1 if bonus else 0))


def category(level: int, susc: int) -> Category:
    """BR-062: matriz nível de chuva × suscetibilidade."""
    return RISK_MATRIX[level][susc - 1]


def rain_factors(
    p1h_max: float | None, p24: float | None, a72: float | None, c: Coefficients
) -> list[Factor]:
    l1h = level_for(p1h_max, c.p1h_thresholds_mm)
    l24 = level_for(p24, c.p24_thresholds_mm)
    factors: list[Factor] = []
    if max(l1h, l24) == 0:
        factors.append(
            Factor(
                "RAIN_NONE",
                "Sem chuva relevante prevista nas próximas 24 h "
                f"(máx. {format_mm(p1h_max or 0.0)} mm em 1 h; "
                f"{format_mm(p24 or 0.0)} mm no total)",
                "info",
            )
        )
    if l1h >= 1 and p1h_max is not None:
        factors.append(
            Factor(
                "RAIN_P1H",
                f"Chuva {RAIN_LEVEL_NAMES[l1h]} prevista ({format_mm(p1h_max)} mm em 1 h)",
                "raises",
            )
        )
    if l24 >= 1 and p24 is not None:
        factors.append(
            Factor(
                "RAIN_P24",
                f"Chuva {RAIN_LEVEL_NAMES[l24]} prevista ({format_mm(p24)} mm em 24 h)",
                "raises",
            )
        )
    if a72 is None:
        factors.append(Factor("ANTECEDENT_NA", "Chuva das 72 h anteriores indisponível", "info"))
    elif a72 >= c.antecedent_threshold_mm and max(l1h, l24) >= 1:
        factors.append(
            Factor(
                "ANTECEDENT",
                f"Chuva estimada nas 72 h anteriores: {format_mm(a72)} mm "
                "(solo encharcado e galerias cheias)",
                "raises",
            )
        )
    else:
        factors.append(
            Factor(
                "ANTECEDENT_LOW",
                f"Chuva estimada nas 72 h anteriores: {format_mm(a72)} mm",
                "info",
            )
        )
    return factors


def susceptibility_factors(
    grade: int, in_flood_extent: bool, nearby_occurrences: int, c: Coefficients
) -> list[Factor]:
    factors = [Factor("GRADE", f"Setor R{grade} vistoriado pela Prefeitura", "raises")]
    if in_flood_extent:
        factors.append(
            Factor(
                "FLOOD_EXTENT",
                f"Setor cruza mancha de inundação de {c.flood_extent_return_period_years} anos "
                "(GeoSampa)",
                "raises",
            )
        )
    if nearby_occurrences > 0:
        plural = "ocorrência registrada" if nearby_occurrences == 1 else "ocorrências registradas"
        raises = nearby_occurrences >= c.occurrence_min_count
        factors.append(
            Factor(
                "OCCURRENCES",
                f"{nearby_occurrences} {plural} a até {format_mm(c.occurrence_radius_m)} m "
                "nos últimos 12 meses",
                "raises" if raises else "info",
            )
        )
    return factors


def unknown_reason(
    *,
    freshness: str,
    point_key: str | None,
    hours_missing: int,
    c: Coefficients,
) -> Factor | None:
    """BR-063: motivo para "desconhecido", ou None se há dados suficientes."""
    if point_key is None:
        return Factor(
            "NO_FORECAST_POINT",
            f"Sem ponto de previsão a até {format_mm(c.max_point_distance_km)} km",
            "unknown",
        )
    if freshness in UNKNOWN_FRESHNESS:
        labels = {
            "STALE": "desatualizada",
            "UNAVAILABLE": "indisponível",
            "UNKNOWN": "ainda não coletada",
        }
        return Factor("FORECAST_" + freshness, f"Previsão {labels[freshness]}", "unknown")
    if hours_missing > c.max_missing_hours:
        return Factor(
            "INCOMPLETE_WINDOW",
            f"Faltam {hours_missing} horas de previsão na janela de {c.window_hours} h",
            "unknown",
        )
    return None

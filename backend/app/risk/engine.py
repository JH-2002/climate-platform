"""Motor v0: entradas -> avaliação por setor (FR-063, NFR-060). Determinístico e puro."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.risk.coefficients import (
    DEFAULT_COEFFICIENTS,
    ENGINE_VERSION,
    Category,
    Coefficients,
)
from app.risk.rules import (
    Factor,
    category,
    rain_factors,
    rain_level,
    susceptibility,
    susceptibility_factors,
    unknown_reason,
)


@dataclass(frozen=True)
class SectorInput:
    sector_id: int
    grade: int
    in_flood_extent: bool
    nearby_occurrences: int
    point_key: str | None
    point_distance_km: float | None


@dataclass(frozen=True)
class RainInput:
    """Chuva de um ponto de previsão. `a72` é None quando faltam horas no histórico."""

    p1h_max: float | None
    p24: float
    hours_available: int
    a72: float | None


@dataclass(frozen=True)
class Assessment:
    sector_id: int
    category: Category
    rain_level: int | None
    susceptibility: int
    p1h_max: float | None
    p24: float | None
    a72: float | None
    point_key: str | None
    point_distance_km: float | None
    in_flood_extent: bool
    nearby_occurrences: int
    factors: tuple[Factor, ...]
    unknown_reason: str | None


@dataclass(frozen=True)
class RunResult:
    engine_version: str
    computed_at: datetime
    valid_until: datetime
    assessments: tuple[Assessment, ...]
    counts: Mapping[str, int] = field(default_factory=dict)


def assess_sector(
    sector: SectorInput,
    rain: RainInput | None,
    freshness: str,
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> Assessment:
    susc = susceptibility(sector.grade, sector.in_flood_extent, sector.nearby_occurrences, c)
    susc_factors = susceptibility_factors(
        sector.grade, sector.in_flood_extent, sector.nearby_occurrences, c
    )
    point_key = sector.point_key if rain is not None else None
    hours_missing = c.window_hours - rain.hours_available if rain is not None else c.window_hours
    reason = unknown_reason(
        freshness=freshness, point_key=point_key, hours_missing=hours_missing, c=c
    )
    distance = sector.point_distance_km if point_key else None
    if reason is not None or rain is None:
        # Nunca rebaixa para "baixo" por falta de dado (BR-063).
        unknown = reason or Factor("NO_FORECAST_POINT", "Sem previsão para o setor", "unknown")
        return Assessment(
            sector_id=sector.sector_id,
            category=Category.UNKNOWN,
            rain_level=None,
            susceptibility=susc,
            p1h_max=rain.p1h_max if rain else None,
            p24=rain.p24 if rain else None,
            a72=rain.a72 if rain else None,
            point_key=point_key,
            point_distance_km=distance,
            in_flood_extent=sector.in_flood_extent,
            nearby_occurrences=sector.nearby_occurrences,
            factors=(unknown, *susc_factors),
            unknown_reason=unknown.code,
        )
    level = rain_level(rain.p1h_max, rain.p24, rain.a72, c)
    return Assessment(
        sector_id=sector.sector_id,
        category=category(level, susc),
        rain_level=level,
        susceptibility=susc,
        p1h_max=rain.p1h_max,
        p24=rain.p24,
        a72=rain.a72,
        point_key=point_key,
        point_distance_km=distance,
        in_flood_extent=sector.in_flood_extent,
        nearby_occurrences=sector.nearby_occurrences,
        factors=(*rain_factors(rain.p1h_max, rain.p24, rain.a72, c), *susc_factors),
        unknown_reason=None,
    )


def assess(
    sectors: Iterable[SectorInput],
    rain_by_point: Mapping[str, RainInput],
    *,
    freshness: str,
    now: datetime,
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> RunResult:
    assessments = tuple(
        assess_sector(
            sector,
            rain_by_point.get(sector.point_key) if sector.point_key else None,
            freshness,
            c,
        )
        for sector in sorted(sectors, key=lambda s: s.sector_id)
    )
    counts = Counter(a.category.value for a in assessments)
    return RunResult(
        engine_version=ENGINE_VERSION,
        computed_at=now,
        valid_until=now + timedelta(hours=c.validity_hours),
        assessments=assessments,
        counts={cat.value: counts.get(cat.value, 0) for cat in Category},
    )

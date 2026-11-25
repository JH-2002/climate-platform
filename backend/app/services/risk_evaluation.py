"""Avaliação retrospectiva do motor de risco (spec 015, FR-211 a FR-215, ADR-018).

Roda o motor puro para cada dia passado com a chuva prevista arquivada e compara com as
ocorrências do GeoSampa por subprefeitura e dia. As faixas de chuva alternativas (calibração)
só são recomendação: o motor oficial não muda.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from geoalchemy2 import Geography
from pydantic import BaseModel
from sqlalchemy import cast, delete, exists, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.open_meteo.forecast import point_key as make_point_key
from app.integrations.open_meteo.historical_forecast import FIRST_DAY
from app.models.tables import (
    flood_extent_areas,
    flood_occurrences,
    forecast_archive_hourly,
    hydro_risk_sectors,
    risk_evaluations,
)
from app.risk.coefficients import DEFAULT_COEFFICIENTS, ENGINE_VERSION, Category, Coefficients
from app.risk.engine import RainInput, SectorInput, assess
from app.risk.evaluation import (
    CALIBRATION_FACTORS,
    DayUnit,
    best_factor,
    by_month,
    contingency,
    day_units,
    nearby_counts,
    normalize_name,
    reliability,
    scaled,
)
from app.services.risk import ForecastPoint, nearest_point, rain_inputs

logger = structlog.get_logger(__name__)
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
KEEP_EVALUATIONS = 10
_PREFILTER_DEG = 0.005


class ContingencyOut(BaseModel):
    hits: int
    misses: int
    false_alarms: int
    correct_negatives: int
    units: int
    events: int
    pod: float | None
    far: float | None
    csi: float | None
    bias: float | None
    base_rate: float | None


class CalibrationOut(ContingencyOut):
    factor: float


class MonthlyOut(ContingencyOut):
    month: str


class ReliabilityOut(BaseModel):
    category: str
    units: int
    with_occurrence: int
    rate: float | None


class PeriodOut(BaseModel):
    start: date | None
    end: date | None
    days: int


class ThresholdsOut(BaseModel):
    p1h_mm: list[float]
    p24_mm: list[float]


class RiskEvaluation(BaseModel):
    """Resposta de `/analytics/risk-evaluation` (spec 015, FR-215)."""

    engine_version: str
    decision: str
    period: PeriodOut
    subprefectures: int
    contingency: ContingencyOut
    reliability: list[ReliabilityOut]
    calibration: list[CalibrationOut]
    best_factor: float | None
    current_thresholds: ThresholdsOut
    monthly: list[MonthlyOut]
    unmatched_subprefectures: list[str]
    sources: list[str]
    computed_at: datetime


@dataclass(frozen=True)
class EvaluationSummary:
    status: str
    days: int = 0
    units: int = 0
    events: int = 0
    csi: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class _Sector:
    sector_id: int
    grade: int
    in_flood: bool
    subprefecture: str
    point_key: str | None
    point_distance_km: float | None


async def _sectors(
    session: AsyncSession, points: Sequence[ForecastPoint], c: Coefficients
) -> list[_Sector]:
    s, f = hydro_risk_sectors, flood_extent_areas
    in_flood = exists().where(
        f.c.active.is_(True),
        f.c.return_period_years == c.flood_extent_return_period_years,
        func.ST_Intersects(f.c.geom, s.c.geom),
    )
    anchor = func.ST_PointOnSurface(s.c.geom)
    rows = await session.execute(
        select(
            s.c.id,
            s.c.grade,
            s.c.subprefecture,
            in_flood.label("in_flood"),
            func.ST_Y(anchor).label("lat"),
            func.ST_X(anchor).label("lon"),
        ).where(s.c.active.is_(True))
    )
    result = []
    for r in rows:
        near = nearest_point(float(r.lat), float(r.lon), points, c.max_point_distance_km)
        result.append(
            _Sector(
                sector_id=int(r.id),
                grade=int(r.grade),
                in_flood=bool(r.in_flood),
                subprefecture=normalize_name(r.subprefecture),
                point_key=near[0] if near else None,
                point_distance_km=round(near[1], 2) if near else None,
            )
        )
    return result


async def _occurrence_days_by_sector(
    session: AsyncSession, c: Coefficients
) -> dict[int, list[date]]:
    """Datas das ocorrências a até `occurrence_radius_m` de cada setor (todas as datas)."""
    o, s = flood_occurrences, hydro_risk_sectors
    rows = await session.execute(
        select(s.c.id, o.c.occurred_on)
        .select_from(o)
        .join(s, func.ST_DWithin(o.c.geom, s.c.geom, _PREFILTER_DEG))
        .where(
            s.c.active.is_(True),
            func.ST_DWithin(
                cast(o.c.geom, Geography), cast(s.c.geom, Geography), c.occurrence_radius_m
            ),
        )
    )
    result: dict[int, list[date]] = defaultdict(list)
    for sector_id, day in rows.tuples():
        result[int(sector_id)].append(day)
    return dict(result)


async def _observed(session: AsyncSession, since: date, until: date) -> set[tuple[date, str]]:
    o = flood_occurrences
    rows = await session.execute(
        select(o.c.occurred_on, o.c.subprefecture).where(
            o.c.occurred_on >= since, o.c.occurred_on <= until
        )
    )
    return {(day, normalize_name(sub)) for day, sub in rows.tuples() if sub}


async def _archive(session: AsyncSession) -> dict[str, dict[datetime, float]]:
    t = forecast_archive_hourly
    rows = await session.execute(select(t.c.point_key, t.c.valid_at, t.c.precipitation_mm))
    series: dict[str, dict[datetime, float]] = defaultdict(dict)
    for key, valid_at, mm in rows.tuples():
        series[str(key)][valid_at.astimezone(UTC)] = float(mm)
    return dict(series)


def local_day_start(day: date) -> datetime:
    return datetime.combine(day, time(0), tzinfo=LOCAL_TZ).astimezone(UTC)


def _complete(rain: dict[str, RainInput], c: Coefficients) -> bool:
    """Dia avaliável: algum ponto com a janela de 24 h e o antecedente completos."""
    return any(
        r.a72 is not None and r.hours_available >= c.window_hours - c.max_missing_hours
        for r in rain.values()
    )


def evaluate(
    sectors: Sequence[_Sector],
    occurrence_days: dict[int, list[date]],
    observed: set[tuple[date, str]],
    archive: dict[str, dict[datetime, float]],
    days: Sequence[date],
    c: Coefficients = DEFAULT_COEFFICIENTS,
    factors: Sequence[float] = CALIBRATION_FACTORS,
) -> dict[str, Any]:
    """Retroteste puro sobre dados já carregados (testável sem banco)."""
    subprefecture_of = {s.sector_id: s.subprefecture for s in sectors if s.subprefecture}
    covered = set(subprefecture_of.values())
    units_by_factor: dict[float, list[DayUnit]] = {f: [] for f in factors}
    evaluated: list[date] = []
    for day in days:
        rain = rain_inputs(archive, local_day_start(day), c)
        if not _complete(rain, c):
            continue
        evaluated.append(day)
        nearby = nearby_counts(occurrence_days, day, c.occurrence_window_days)
        inputs = [
            SectorInput(
                sector_id=s.sector_id,
                grade=s.grade,
                in_flood_extent=s.in_flood,
                nearby_occurrences=nearby.get(s.sector_id, 0),
                point_key=s.point_key,
                point_distance_km=s.point_distance_km,
            )
            for s in sectors
        ]
        for factor in factors:
            result = assess(
                inputs, rain, freshness="FRESH", now=local_day_start(day), c=scaled(c, factor)
            )
            categories: dict[int, Category] = {a.sector_id: a.category for a in result.assessments}
            units_by_factor[factor].extend(day_units(day, categories, subprefecture_of, observed))

    current = units_by_factor.get(1.0, [])
    table = contingency(current)
    calibration: list[dict[str, Any]] = []
    scores: list[tuple[float, float | None]] = []
    for factor, units in units_by_factor.items():
        t = contingency(units)
        calibration.append({"factor": factor, **t.as_dict()})
        scores.append((factor, t.csi))
    best = best_factor(scores)
    unmatched = sorted({sub for _, sub in observed} - covered)
    return {
        "engine_version": ENGINE_VERSION,
        "decision": "HIGH_OR_CRITICAL",
        "period": {
            "start": evaluated[0].isoformat() if evaluated else None,
            "end": evaluated[-1].isoformat() if evaluated else None,
            "days": len(evaluated),
        },
        "subprefectures": len(covered),
        "contingency": table.as_dict(),
        "reliability": reliability(current),
        "calibration": calibration,
        "best_factor": best,
        "current_thresholds": {
            "p1h_mm": list(c.p1h_thresholds_mm),
            "p24_mm": list(c.p24_thresholds_mm),
        },
        "monthly": by_month(current),
        "unmatched_subprefectures": unmatched,
        "sources": [
            "Previsão arquivada: Open-Meteo.com (CC BY 4.0)",
            "Ocorrências e setores: GeoSampa — Prefeitura de São Paulo",
        ],
    }


async def compute_risk_evaluation(
    session: AsyncSession,
    now: datetime,
    points: Sequence[tuple[float, float]],
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> EvaluationSummary:
    """Recalcula a avaliação e guarda o resultado (as 10 últimas ficam)."""
    yesterday = now.astimezone(LOCAL_TZ).date() - timedelta(days=1)
    first = FIRST_DAY + timedelta(days=3)  # precisa de 72 h antecedentes
    try:
        forecast_points = [
            ForecastPoint(make_point_key(lat, lon), lat, lon, now) for lat, lon in points
        ]
        sectors = await _sectors(session, forecast_points, c)
        if not sectors:
            raise ValueError("nenhum setor de risco sincronizado do GeoSampa")
        archive = await _archive(session)
        if not archive:
            raise ValueError("arquivo de previsões ainda vazio")
        occurrence_days = await _occurrence_days_by_sector(session, c)
        observed = await _observed(session, first, yesterday)
        days = [first + timedelta(days=i) for i in range((yesterday - first).days + 1)]
        result = evaluate(sectors, occurrence_days, observed, archive, days, c)
        if not result["period"]["days"]:
            raise ValueError("nenhum dia com chuva arquivada completa")
    except Exception as exc:
        await session.rollback()
        error = f"{type(exc).__name__}: {exc}"[:500]
        await session.execute(
            insert(risk_evaluations).values(
                computed_at=now, engine_version=ENGINE_VERSION, status="FAILED", error=error
            )
        )
        await session.commit()
        logger.warning("risk_evaluation_failed", error=error)
        return EvaluationSummary("FAILED", error=error)

    result["computed_at"] = now.isoformat()
    await session.execute(
        insert(risk_evaluations).values(
            computed_at=now,
            engine_version=ENGINE_VERSION,
            period_start=date.fromisoformat(result["period"]["start"]),
            period_end=date.fromisoformat(result["period"]["end"]),
            status="SUCCESS",
            result=result,
        )
    )
    keep = (
        select(risk_evaluations.c.id)
        .order_by(risk_evaluations.c.computed_at.desc())
        .limit(KEEP_EVALUATIONS)
        .scalar_subquery()
    )
    await session.execute(delete(risk_evaluations).where(risk_evaluations.c.id.not_in(keep)))
    await session.commit()
    table = result["contingency"]
    logger.info("risk_evaluation_computed", days=result["period"]["days"], csi=table["csi"])
    return EvaluationSummary(
        "SUCCESS", result["period"]["days"], table["units"], table["events"], table["csi"]
    )


async def latest_evaluation(session: AsyncSession) -> RiskEvaluation | None:
    row = (
        await session.execute(
            select(risk_evaluations.c.result)
            .where(risk_evaluations.c.status == "SUCCESS")
            .order_by(risk_evaluations.c.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return RiskEvaluation.model_validate(row) if row else None

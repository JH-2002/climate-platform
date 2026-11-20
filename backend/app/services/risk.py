"""Risco de alagamento (spec 005): monta as entradas, roda o motor, grava e consulta.

As funções puras (distância, ponto mais próximo, chuva por ponto) ficam separadas das
consultas. O motor em `app.risk` não conhece o banco (NFR-060).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from geoalchemy2 import Geography
from pydantic import BaseModel
from sqlalchemy import case, cast, exists, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    data_sources,
    flood_extent_areas,
    flood_occurrences,
    hydro_risk_sectors,
    risk_assessments,
    risk_runs,
    weather_forecasts,
)
from app.risk.coefficients import DEFAULT_COEFFICIENTS, ENGINE_VERSION, Category, Coefficients
from app.risk.engine import RainInput, RunResult, SectorInput, assess
from app.services.forecast import FORECAST_SOURCE, current_hour
from app.services.freshness import classify_freshness

logger = structlog.get_logger(__name__)

ENGINE_SOURCE = "flood-risk-engine"
SECTORS_SOURCE = "geosampa-risk-sectors"
OFFICIAL_URL = "https://geosampa.prefeitura.sp.gov.br"
DISCLAIMER = (
    "Estimativa experimental do sistema, heurística e não validada. Não é alerta oficial. "
    "Em emergência, ligue 199 (Defesa Civil)."
)
ATTRIBUTION = (
    "Setores, manchas e ocorrências: GeoSampa — Prefeitura de São Paulo · "
    "Previsão: Open-Meteo.com (CC BY 4.0)"
)
CATEGORY_RANK = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1, "UNKNOWN": 0}
# Pré-filtro em graus (~550 m) para usar o índice espacial antes da distância em metros.
_PREFILTER_DEG = 0.005
# Tolerância de simplificação dos polígonos enviados ao mapa (~5 m), NFR-062.
SIMPLIFY_TOLERANCE_DEG = 0.00005
MAX_NEARBY_OCCURRENCES = 20


# --- funções puras ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ForecastPoint:
    point_key: str
    latitude: float
    longitude: float
    issued_at: datetime


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_point(
    lat: float, lon: float, points: Sequence[ForecastPoint], max_km: float
) -> tuple[str, float] | None:
    best: tuple[str, float] | None = None
    for p in points:
        d = haversine_km(lat, lon, p.latitude, p.longitude)
        if d <= max_km and (best is None or d < best[1]):
            best = (p.point_key, d)
    return best


def rain_inputs(
    hourly: Mapping[str, Mapping[datetime, float]],
    start: datetime,
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> dict[str, RainInput]:
    """Chuva por ponto: janela [start, start+24 h) e antecedente [start-72 h, start)."""
    result: dict[str, RainInput] = {}
    for key, series in hourly.items():
        window = [
            series[t] for h in range(c.window_hours) if (t := start + timedelta(hours=h)) in series
        ]
        past = [
            series[t]
            for h in range(1, c.antecedent_hours + 1)
            if (t := start - timedelta(hours=h)) in series
        ]
        a72 = round(sum(past), 2) if len(past) >= c.antecedent_hours - c.max_missing_hours else None
        result[key] = RainInput(
            p1h_max=round(max(window), 2) if window else None,
            p24=round(sum(window), 2),
            hours_available=len(window),
            a72=a72,
        )
    return result


# --- montagem das entradas -------------------------------------------------------------------


async def _forecast_points(session: AsyncSession) -> list[ForecastPoint]:
    t = weather_forecasts
    rows = (
        await session.execute(
            select(
                t.c.point_key,
                func.ST_Y(func.geometry(t.c.point)).label("latitude"),
                func.ST_X(func.geometry(t.c.point)).label("longitude"),
                func.max(t.c.issued_at).label("issued_at"),
            )
            .join(data_sources, data_sources.c.id == t.c.source_id)
            .where(data_sources.c.code == FORECAST_SOURCE)
            .group_by(t.c.point_key, t.c.point)
        )
    ).all()
    return [
        ForecastPoint(r.point_key, float(r.latitude), float(r.longitude), r.issued_at) for r in rows
    ]


async def _hourly_precipitation(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[str, dict[datetime, float]]:
    t = weather_forecasts
    rows = await session.execute(
        select(t.c.point_key, t.c.valid_at, t.c.value)
        .join(data_sources, data_sources.c.id == t.c.source_id)
        .where(
            data_sources.c.code == FORECAST_SOURCE,
            t.c.resolution == "hourly",
            t.c.variable == "precipitation",
            t.c.valid_at >= start,
            t.c.valid_at < end,
        )
    )
    series: dict[str, dict[datetime, float]] = defaultdict(dict)
    for r in rows:
        series[r.point_key][r.valid_at.astimezone(UTC)] = float(r.value)
    return dict(series)


async def source_freshness(session: AsyncSession, code: str, now: datetime) -> str:
    row = (
        await session.execute(select(data_sources).where(data_sources.c.code == code))
    ).one_or_none()
    if row is None:
        return "UNKNOWN"
    return classify_freshness(
        now=now,
        last_success_at=row.last_success_at,
        expected_interval_s=row.expected_interval_s,
        last_run_status=row.last_status,
        enabled=row.enabled,
    ).freshness


def _occurrence_window(now: datetime, c: Coefficients) -> tuple[date, date]:
    today = now.astimezone(UTC).date()
    return today - timedelta(days=c.occurrence_window_days), today


def _nearby_occurrences_condition(c: Coefficients, since: date, until: date) -> Any:
    o, s = flood_occurrences, hydro_risk_sectors
    return (
        o.c.occurred_on >= since,
        o.c.occurred_on <= until,
        func.ST_DWithin(o.c.geom, s.c.geom, _PREFILTER_DEG),
        func.ST_DWithin(
            cast(o.c.geom, Geography), cast(s.c.geom, Geography), c.occurrence_radius_m
        ),
    )


async def _sector_rows(session: AsyncSession, now: datetime, c: Coefficients) -> list[Any]:
    s, f, o = hydro_risk_sectors, flood_extent_areas, flood_occurrences
    since, until = _occurrence_window(now, c)
    in_flood = exists().where(
        f.c.active.is_(True),
        f.c.return_period_years == c.flood_extent_return_period_years,
        func.ST_Intersects(f.c.geom, s.c.geom),
    )
    nearby = (
        select(func.count())
        .select_from(o)
        .where(*_nearby_occurrences_condition(c, since, until))
        .scalar_subquery()
    )
    anchor = func.ST_PointOnSurface(s.c.geom)
    result = await session.execute(
        select(
            s.c.id,
            s.c.grade,
            in_flood.label("in_flood"),
            nearby.label("nearby"),
            func.ST_Y(anchor).label("latitude"),
            func.ST_X(anchor).label("longitude"),
        ).where(s.c.active.is_(True))
    )
    return list(result.all())


@dataclass(frozen=True)
class RiskRunSummary:
    run_id: int
    status: str
    sector_count: int
    counts: Mapping[str, int]
    error: str | None = None


async def compute_flood_risk(
    session: AsyncSession, now: datetime, c: Coefficients = DEFAULT_COEFFICIENTS
) -> RiskRunSummary:
    """Roda o motor e grava a execução (FR-064). Falhas também são gravadas."""
    start = current_hour(now)
    freshness = await source_freshness(session, FORECAST_SOURCE, now)
    points = await _forecast_points(session)
    issued_at = max((p.issued_at for p in points), default=None)
    try:
        rows = await _sector_rows(session, now, c)
        if not rows:
            raise ValueError("nenhum setor de risco sincronizado do GeoSampa")
        hourly = await _hourly_precipitation(
            session,
            start - timedelta(hours=c.antecedent_hours),
            start + timedelta(hours=c.window_hours),
        )
        rain = rain_inputs(hourly, start, c)
        sectors = []
        for r in rows:
            near = nearest_point(
                float(r.latitude), float(r.longitude), points, c.max_point_distance_km
            )
            sectors.append(
                SectorInput(
                    sector_id=int(r.id),
                    grade=int(r.grade),
                    in_flood_extent=bool(r.in_flood),
                    nearby_occurrences=int(r.nearby),
                    point_key=near[0] if near else None,
                    point_distance_km=round(near[1], 2) if near else None,
                )
            )
        result = assess(sectors, rain, freshness=freshness, now=now, c=c)
    except Exception as exc:
        await session.rollback()
        error = f"{type(exc).__name__}: {exc}"[:500]
        run_id = await _insert_run(session, now, c, freshness, issued_at, "FAILED", 0, error)
        await _update_engine_source(session, now, "FAILED", error)
        await session.commit()
        logger.warning("flood_risk_failed", run_id=run_id, error=error)
        return RiskRunSummary(run_id, "FAILED", 0, {}, error)

    run_id = await _insert_run(
        session, now, c, freshness, issued_at, "SUCCESS", len(result.assessments), None
    )
    await _insert_assessments(session, run_id, result)
    await _update_engine_source(session, now, "SUCCESS", None)
    await session.commit()
    logger.info("flood_risk_computed", run_id=run_id, freshness=freshness, **result.counts)
    return RiskRunSummary(run_id, "SUCCESS", len(result.assessments), result.counts)


async def _insert_run(
    session: AsyncSession,
    now: datetime,
    c: Coefficients,
    freshness: str,
    issued_at: datetime | None,
    status: str,
    count: int,
    error: str | None,
) -> int:
    return int(
        (
            await session.execute(
                insert(risk_runs)
                .values(
                    engine_version=ENGINE_VERSION,
                    computed_at=now,
                    valid_until=now + timedelta(hours=c.validity_hours),
                    forecast_issued_at=issued_at,
                    forecast_freshness=freshness,
                    status=status,
                    sector_count=count,
                    params=c.as_params(),
                    error_summary=error,
                )
                .returning(risk_runs.c.id)
            )
        ).scalar_one()
    )


async def _insert_assessments(session: AsyncSession, run_id: int, result: RunResult) -> None:
    rows = [
        {
            "run_id": run_id,
            "sector_id": a.sector_id,
            "category": a.category.value,
            "rain_level": a.rain_level,
            "susceptibility": a.susceptibility,
            "p1h_max_mm": a.p1h_max,
            "p24_mm": a.p24,
            "a72_mm": a.a72,
            "forecast_point_key": a.point_key,
            "forecast_distance_km": a.point_distance_km,
            "in_flood_extent_100y": a.in_flood_extent,
            "nearby_occurrences_12m": a.nearby_occurrences,
            "factors": [f.as_dict() for f in a.factors],
            "unknown_reason": a.unknown_reason,
        }
        for a in result.assessments
    ]
    for i in range(0, len(rows), 500):
        await session.execute(insert(risk_assessments), rows[i : i + 500])


async def _update_engine_source(
    session: AsyncSession, now: datetime, status: str, error: str | None
) -> None:
    values: dict[str, Any] = {"last_attempt_at": now, "last_status": status, "last_error": error}
    if status == "SUCCESS":
        values["last_success_at"] = now
    await session.execute(
        update(data_sources).where(data_sources.c.code == ENGINE_SOURCE).values(values)
    )


# --- consultas (API) -------------------------------------------------------------------------


class Factor(BaseModel):
    code: str
    text: str
    effect: str


class RunInfo(BaseModel):
    id: int
    engine_version: str
    computed_at: datetime
    valid_until: datetime
    forecast_issued_at: datetime | None
    forecast_freshness: str
    stale: bool


class RiskSummary(BaseModel):
    run: RunInfo | None
    counts: dict[str, int]
    sectors_freshness: str
    disclaimer: str = DISCLAIMER
    attribution: str = ATTRIBUTION
    experimental: bool = True


class RiskArea(BaseModel):
    id: int
    code: str
    name: str | None
    subprefecture: str | None
    basin: str | None
    grade: int
    households: int | None
    category: str
    rain_level: int | None
    susceptibility: int
    p1h_max_mm: float | None
    p24_mm: float | None
    a72_mm: float | None
    in_flood_extent_100y: bool
    nearby_occurrences_12m: int
    factors: list[Factor]
    unknown_reason: str | None


class Occurrence(BaseModel):
    type: str
    occurred_on: date
    subprefecture: str | None
    distance_m: float


class RiskInput(BaseModel):
    name: str
    value: float | None
    unit: str
    kind: str
    source: str


class RiskAreaDetail(RiskArea):
    processes: list[str]
    inspected_on: date | None
    latitude: float
    longitude: float
    forecast_point_key: str | None
    forecast_distance_km: float | None
    inputs: list[RiskInput]
    nearby_occurrences: list[Occurrence]
    run: RunInfo
    official_url: str = OFFICIAL_URL
    disclaimer: str = DISCLAIMER


def _run_info(row: Any, now: datetime, c: Coefficients) -> RunInfo:
    return RunInfo(
        id=row.id,
        engine_version=row.engine_version,
        computed_at=row.computed_at,
        valid_until=row.valid_until,
        forecast_issued_at=row.forecast_issued_at,
        forecast_freshness=row.forecast_freshness,
        stale=now - row.computed_at > timedelta(hours=c.stale_after_hours),
    )


async def latest_run(session: AsyncSession) -> Any | None:
    return (
        await session.execute(
            select(risk_runs)
            .where(risk_runs.c.status == "SUCCESS")
            .order_by(risk_runs.c.computed_at.desc(), risk_runs.c.id.desc())
            .limit(1)
        )
    ).one_or_none()


async def risk_summary(
    session: AsyncSession, now: datetime, c: Coefficients = DEFAULT_COEFFICIENTS
) -> RiskSummary:
    run = await latest_run(session)
    counts = {cat.value: 0 for cat in Category}
    if run is not None:
        rows = await session.execute(
            select(risk_assessments.c.category, func.count())
            .where(risk_assessments.c.run_id == run.id)
            .group_by(risk_assessments.c.category)
        )
        for category, total in rows.tuples():
            counts[category] = int(total)
    return RiskSummary(
        run=_run_info(run, now, c) if run is not None else None,
        counts=counts,
        sectors_freshness=await source_freshness(session, SECTORS_SOURCE, now),
    )


def _rank() -> Any:
    a = risk_assessments
    return case(*((a.c.category == k, v) for k, v in CATEGORY_RANK.items()), else_=0)


def _area_columns() -> list[Any]:
    s, a = hydro_risk_sectors, risk_assessments
    return [
        s.c.id,
        s.c.source_code.label("code"),
        s.c.area_name.label("name"),
        s.c.subprefecture,
        s.c.basin,
        s.c.grade,
        s.c.households,
        a.c.category,
        a.c.rain_level,
        a.c.susceptibility,
        a.c.p1h_max_mm,
        a.c.p24_mm,
        a.c.a72_mm,
        a.c.in_flood_extent_100y,
        a.c.nearby_occurrences_12m,
        a.c.factors,
        a.c.unknown_reason,
    ]


def _area(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "subprefecture": row.subprefecture,
        "basin": row.basin,
        "grade": row.grade,
        "households": row.households,
        "category": row.category,
        "rain_level": row.rain_level,
        "susceptibility": row.susceptibility,
        "p1h_max_mm": row.p1h_max_mm,
        "p24_mm": row.p24_mm,
        "a72_mm": row.a72_mm,
        "in_flood_extent_100y": row.in_flood_extent_100y,
        "nearby_occurrences_12m": row.nearby_occurrences_12m,
        "factors": row.factors,
        "unknown_reason": row.unknown_reason,
    }


async def list_risk_areas(
    session: AsyncSession,
    *,
    category: str | None,
    subprefecture: str | None,
    limit: int,
    offset: int,
) -> tuple[list[RiskArea], int]:
    run = await latest_run(session)
    if run is None:
        return [], 0
    s, a = hydro_risk_sectors, risk_assessments
    conditions = [a.c.run_id == run.id, s.c.active.is_(True)]
    if category:
        conditions.append(a.c.category == category)
    if subprefecture:
        conditions.append(s.c.subprefecture == subprefecture)
    base = select(*_area_columns()).join(a, a.c.sector_id == s.c.id).where(*conditions)
    total = int(
        (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    )
    rows = await session.execute(
        base.order_by(
            _rank().desc(),
            a.c.rain_level.desc().nulls_last(),
            a.c.susceptibility.desc(),
            s.c.households.desc().nulls_last(),
            s.c.source_code,
        )
        .limit(limit)
        .offset(offset)
    )
    return [RiskArea.model_validate(_area(r)) for r in rows], total


async def list_subprefectures(session: AsyncSession) -> list[str]:
    s = hydro_risk_sectors
    rows = await session.execute(
        select(s.c.subprefecture)
        .where(s.c.active.is_(True), s.c.subprefecture.is_not(None))
        .distinct()
        .order_by(s.c.subprefecture)
    )
    return [r for (r,) in rows.tuples()]


async def risk_area_detail(
    session: AsyncSession, sector_id: int, now: datetime, c: Coefficients = DEFAULT_COEFFICIENTS
) -> RiskAreaDetail | None:
    run = await latest_run(session)
    if run is None:
        return None
    s, a, o = hydro_risk_sectors, risk_assessments, flood_occurrences
    anchor = func.ST_PointOnSurface(s.c.geom)
    row = (
        await session.execute(
            select(
                *_area_columns(),
                s.c.processes,
                s.c.inspected_on,
                func.ST_Y(anchor).label("latitude"),
                func.ST_X(anchor).label("longitude"),
                a.c.forecast_point_key,
                a.c.forecast_distance_km,
            )
            .join(a, a.c.sector_id == s.c.id)
            .where(a.c.run_id == run.id, s.c.id == sector_id)
        )
    ).one_or_none()
    if row is None:
        return None
    since, until = _occurrence_window(now, c)
    distance = func.ST_Distance(cast(o.c.geom, Geography), cast(s.c.geom, Geography))
    occ_rows = await session.execute(
        select(o.c.occurrence_type, o.c.occurred_on, o.c.subprefecture, distance.label("d"))
        .select_from(o.join(s, s.c.id == sector_id))
        .where(*_nearby_occurrences_condition(c, since, until))
        .order_by(o.c.occurred_on.desc())
        .limit(MAX_NEARBY_OCCURRENCES)
    )
    forecast = "Open-Meteo.com (CC BY 4.0)"
    inputs = [
        RiskInput(
            name="Maior chuva prevista em 1 h (próximas 24 h)",
            value=row.p1h_max_mm,
            unit="mm",
            kind="FORECAST",
            source=forecast,
        ),
        RiskInput(
            name="Chuva prevista em 24 h",
            value=row.p24_mm,
            unit="mm",
            kind="FORECAST",
            source=forecast,
        ),
        RiskInput(
            name="Chuva estimada nas 72 h anteriores",
            value=row.a72_mm,
            unit="mm",
            kind="MODELED",
            source=forecast,
        ),
        RiskInput(
            name="Grau do setor (R1–R4)",
            value=float(row.grade),
            unit="grau",
            kind="OBSERVED",
            source="GeoSampa — vistoria da Prefeitura",
        ),
    ]
    return RiskAreaDetail.model_validate(
        {
            **_area(row),
            "processes": list(row.processes or []),
            "inspected_on": row.inspected_on,
            "latitude": float(row.latitude),
            "longitude": float(row.longitude),
            "forecast_point_key": row.forecast_point_key,
            "forecast_distance_km": row.forecast_distance_km,
            "inputs": inputs,
            "nearby_occurrences": [
                Occurrence(
                    type=r.occurrence_type,
                    occurred_on=r.occurred_on,
                    subprefecture=r.subprefecture,
                    distance_m=round(float(r.d), 1),
                )
                for r in occ_rows
            ],
            "run": _run_info(run, now, c),
        }
    )


async def nearest_risk_area(
    session: AsyncSession, lat: float, lon: float, max_km: float, now: datetime
) -> tuple[RiskArea, float] | None:
    """Setor mais próximo de uma coordenada, até `max_km` (FR-071)."""
    run = await latest_run(session)
    if run is None:
        return None
    s, a = hydro_risk_sectors, risk_assessments
    origin = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    distance = func.ST_Distance(cast(s.c.geom, Geography), origin)
    row = (
        await session.execute(
            select(*_area_columns(), distance.label("distance_m"))
            .join(a, a.c.sector_id == s.c.id)
            .where(
                a.c.run_id == run.id,
                s.c.active.is_(True),
                func.ST_DWithin(cast(s.c.geom, Geography), origin, max_km * 1000.0),
            )
            .order_by(distance)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    return RiskArea.model_validate(_area(row)), float(row.distance_m)


async def risk_area_features(session: AsyncSession) -> list[dict[str, Any]]:
    """Polígonos simplificados com a categoria da última execução (FR-068, NFR-062)."""
    run = await latest_run(session)
    if run is None:
        return []
    s, a = hydro_risk_sectors, risk_assessments
    geometry = func.ST_AsGeoJSON(
        func.ST_SimplifyPreserveTopology(s.c.geom, SIMPLIFY_TOLERANCE_DEG), 6
    )
    rows = await session.execute(
        select(
            s.c.id,
            s.c.source_code,
            s.c.area_name,
            s.c.subprefecture,
            s.c.grade,
            s.c.households,
            a.c.category,
            a.c.rain_level,
            a.c.p1h_max_mm,
            a.c.p24_mm,
            geometry.label("geometry"),
        )
        .join(a, a.c.sector_id == s.c.id)
        .where(a.c.run_id == run.id, s.c.active.is_(True))
        .order_by(s.c.id)
    )
    return [
        {
            "type": "Feature",
            "id": r.id,
            "geometry": json.loads(r.geometry),
            "properties": {
                "id": r.id,
                "code": r.source_code,
                "name": r.area_name,
                "subprefecture": r.subprefecture,
                "grade": r.grade,
                "households": r.households,
                "category": r.category,
                "rain_level": r.rain_level,
                "p1h_max_mm": r.p1h_max_mm,
                "p24_mm": r.p24_mm,
                "kind": "DERIVED",
            },
        }
        for r in rows
    ]


async def occurrence_features(
    session: AsyncSession, now: datetime, c: Coefficients = DEFAULT_COEFFICIENTS
) -> list[dict[str, Any]]:
    o = flood_occurrences
    since, until = _occurrence_window(now, c)
    rows = await session.execute(
        select(
            o.c.id,
            o.c.occurrence_type,
            o.c.occurred_on,
            o.c.subprefecture,
            func.ST_X(o.c.geom).label("lon"),
            func.ST_Y(o.c.geom).label("lat"),
        )
        .where(o.c.occurred_on >= since, o.c.occurred_on <= until)
        .order_by(o.c.occurred_on.desc(), o.c.id)
    )
    return [
        {
            "type": "Feature",
            "id": r.id,
            "geometry": {"type": "Point", "coordinates": [round(r.lon, 6), round(r.lat, 6)]},
            "properties": {
                "type": r.occurrence_type,
                "occurred_on": r.occurred_on.isoformat(),
                "subprefecture": r.subprefecture,
                "kind": "OBSERVED",
            },
        }
        for r in rows
    ]

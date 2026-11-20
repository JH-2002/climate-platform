"""Laboratório de simulação (spec 007): monta os setores, roda o motor, compara e grava.

Os resultados ficam em `simulation_runs` e `simulation_results` e nunca entram nas tabelas,
telas ou indicadores do risco real (BR-101).
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, cast

import structlog
from pydantic import BaseModel
from sqlalchemy import CursorResult, case, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    hydro_risk_sectors,
    risk_assessments,
    simulation_results,
    simulation_runs,
)
from app.risk.coefficients import DEFAULT_COEFFICIENTS, Category, Coefficients
from app.risk.engine import RainInput
from app.risk.rules import UNKNOWN_FRESHNESS
from app.services.forecast import FORECAST_SOURCE, current_hour
from app.services.risk import (
    CATEGORY_RANK,
    SIMPLIFY_TOLERANCE_DEG,
    forecast_points,
    hourly_precipitation_by_point,
    latest_run,
    nearest_point,
    rain_inputs,
    sector_rows,
    source_freshness,
)
from app.simulation.engine import SimSector, SimulationResult, sectors_fingerprint, simulate
from app.simulation.scenario import (
    PATTERN_LABELS,
    PRESETS,
    Hybrid,
    Pattern,
    Scenario,
    Uncertainty,
)

logger = structlog.get_logger(__name__)

BANNER = "SIMULAÇÃO — cenário hipotético, não é previsão nem alerta"
DISCLAIMER = (
    "Cenário hipotético avaliado pelo motor de risco v0 (experimental, não calibrado e sem "
    "hidrologia). Não é previsão nem alerta. Em emergência, ligue 199 (Defesa Civil)."
)
RETENTION_DAYS = 30
MAX_STORED_RUNS = 500
TOP_SUBPREFECTURES = 8
HIGH_OR_ABOVE = frozenset({Category.HIGH.value, Category.CRITICAL.value})


class SimulationUnavailableError(RuntimeError):
    """Sem setores sincronizados: não há o que simular."""


class HybridUnavailableError(RuntimeError):
    """Previsão vencida ou indisponível: o modo HYBRID é recusado (AC-105)."""


HYBRID_BANNER = (
    "SIMULAÇÃO A PARTIR DA PREVISÃO REAL — cenário hipotético, não é previsão nem alerta"
)
FRESHNESS_LABELS = {
    "STALE": "desatualizada",
    "UNAVAILABLE": "indisponível",
    "UNKNOWN": "ainda não coletada",
}


# --- modelos de resposta ---------------------------------------------------------------------


class PresetOut(BaseModel):
    code: str
    name: str
    description: str
    origin: str
    scenario: dict[str, Any]


class RealRunRef(BaseModel):
    id: int
    computed_at: datetime
    stale: bool


class SubprefectureChange(BaseModel):
    name: str
    sectors: int
    high_or_above_simulated: int
    high_or_above_real: int
    raised: int


class Comparison(BaseModel):
    real_run: RealRunRef | None
    real_counts: dict[str, int]
    raised: int
    lowered: int
    unchanged: int
    not_comparable: int
    subprefectures: list[SubprefectureChange]


class RepeatCheck(BaseModel):
    """FR-110: a repetição bate com a original? Se não, por quê."""

    original_id: uuid.UUID
    same_engine_versions: bool
    same_sectors: bool
    same_forecast: bool | None
    identical_results: bool


class RunListItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    mode: str
    scenario_text: str
    preset: str | None
    seed: int | None
    members: int
    high_or_above: int
    unknown: int


class SimulationRun(BaseModel):
    id: uuid.UUID
    created_at: datetime
    kind: str
    mode: str
    scenario: dict[str, Any]
    scenario_text: str
    preset: str | None
    seed: int | None
    members: int
    simulation_engine_version: str
    risk_engine_version: str
    sectors_fingerprint: str
    sectors_changed: bool
    sector_count: int
    counts: dict[str, int]
    comparison: Comparison
    duration_ms: int
    forecast_issued_at: datetime | None
    ensemble: dict[str, Any] | None
    repeat_of: uuid.UUID | None
    repeat_check: RepeatCheck | None
    banner: str = BANNER
    disclaimer: str = DISCLAIMER


class Factor(BaseModel):
    code: str
    text: str
    effect: str


class SimulatedSector(BaseModel):
    id: int
    code: str
    name: str | None
    subprefecture: str | None
    grade: int
    households: int | None
    category: str
    real_category: str | None
    rain_level: int | None
    susceptibility: int
    p1h_max_mm: float | None
    p24_mm: float | None
    a72_mm: float | None
    rain_factor: float
    distance_km: float | None
    p_high: float | None
    p_critical: float | None
    factors: list[Factor]


# --- funções puras ---------------------------------------------------------------------------


def _mm(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def scenario_text(scenario: Mapping[str, Any]) -> str:
    """Resumo legível do cenário, usado no histórico e no topo do resultado."""
    hybrid = scenario.get("hybrid")
    storm_parts: list[str] = []
    if hybrid is None or hybrid.get("add_storm"):
        pattern = PATTERN_LABELS[Pattern(scenario["pattern"])]
        hours = "1 hora" if scenario["duration_h"] == 1 else f"{scenario['duration_h']} horas"
        cell = scenario.get("cell")
        where = f"numa célula de {_mm(cell['radius_km'])} km" if cell else "na cidade inteira"
        storm_parts.append(f"{_mm(scenario['total_mm'])} mm em {hours}, {pattern}, {where}")
    if hybrid is None:
        text = f"{storm_parts[0]}; {_mm(scenario['antecedent_mm'])} mm nas 72 h anteriores"
    else:
        pct = round(hybrid["multiplier"] * 100)
        text = f"previsão real × {pct}%"
        if storm_parts:
            text += f" mais {storm_parts[0]}"
        text += "; chuva das 72 h anteriores real"
    unc = scenario.get("uncertainty")
    if unc and unc.get("members", 1) > 1:
        text += (
            f"; {unc['members']} variações (intensidade ±{_mm(unc['intensity_pct'])}%, "
            f"centro até {_mm(unc['shift_km'])} km)"
        )
    return text


def compare(
    result: SimulationResult,
    real: Mapping[int, str],
    subprefecture_of: Mapping[int, str | None],
) -> dict[str, Any]:
    """FR-106: o que muda em relação à estimativa real. Real desconhecido não é comparado."""
    raised = lowered = unchanged = not_comparable = 0
    per_sub: dict[str, Counter[str]] = {}
    for outcome in result.outcomes:
        sector_id = outcome.assessment.sector_id
        simulated = outcome.assessment.category.value
        actual = real.get(sector_id)
        name = subprefecture_of.get(sector_id) or "Sem subprefeitura"
        counter = per_sub.setdefault(name, Counter())
        counter["sectors"] += 1
        counter["sim_high"] += simulated in HIGH_OR_ABOVE
        if actual is None or actual == Category.UNKNOWN.value:
            not_comparable += 1
            continue
        counter["real_high"] += actual in HIGH_OR_ABOVE
        delta = CATEGORY_RANK[simulated] - CATEGORY_RANK[actual]
        if delta > 0:
            raised += 1
            counter["raised"] += 1
        elif delta < 0:
            lowered += 1
        else:
            unchanged += 1
    subs = sorted(
        (
            SubprefectureChange(
                name=name,
                sectors=c["sectors"],
                high_or_above_simulated=c["sim_high"],
                high_or_above_real=c["real_high"],
                raised=c["raised"],
            )
            for name, c in per_sub.items()
        ),
        key=lambda s: (-s.high_or_above_simulated, -s.raised, s.name),
    )
    real_counts = Counter(real.values())
    return {
        "real_counts": {cat.value: real_counts.get(cat.value, 0) for cat in Category},
        "raised": raised,
        "lowered": lowered,
        "unchanged": unchanged,
        "not_comparable": not_comparable,
        "subprefectures": [
            s.model_dump()
            for s in subs[:TOP_SUBPREFECTURES]
            if s.high_or_above_simulated or s.raised
        ],
    }


# --- consultas -------------------------------------------------------------------------------


async def load_sectors(
    session: AsyncSession, now: datetime, c: Coefficients = DEFAULT_COEFFICIENTS
) -> list[SimSector]:
    rows = await sector_rows(session, now, c)
    return [
        SimSector(
            sector_id=int(r.id),
            grade=int(r.grade),
            in_flood_extent=bool(r.in_flood),
            nearby_occurrences=int(r.nearby),
            latitude=float(r.latitude),
            longitude=float(r.longitude),
        )
        for r in rows
    ]


async def _subprefectures(session: AsyncSession) -> dict[int, str | None]:
    s = hydro_risk_sectors
    rows = await session.execute(select(s.c.id, s.c.subprefecture).where(s.c.active.is_(True)))
    return {int(i): sub for i, sub in rows.tuples()}


async def _real_categories(session: AsyncSession) -> tuple[Any | None, dict[int, str]]:
    run = await latest_run(session)
    if run is None:
        return None, {}
    a = risk_assessments
    rows = await session.execute(select(a.c.sector_id, a.c.category).where(a.c.run_id == run.id))
    return run, {int(i): cat for i, cat in rows.tuples()}


async def purge_old_runs(session: AsyncSession, now: datetime) -> int:
    """NFR-102: 30 dias e no máximo 500 execuções; as mais antigas saem primeiro."""
    r = simulation_runs
    old = cast(
        "CursorResult[Any]",
        await session.execute(
            delete(r).where(r.c.created_at < now - timedelta(days=RETENTION_DAYS))
        ),
    )
    keep = select(r.c.id).order_by(r.c.created_at.desc()).limit(MAX_STORED_RUNS)
    extra = cast(
        "CursorResult[Any]",
        await session.execute(delete(r).where(r.c.id.not_in(keep.scalar_subquery()))),
    )
    return int(old.rowcount or 0) + int(extra.rowcount or 0)


async def _forecast_base(
    session: AsyncSession, sectors: Sequence[SimSector], now: datetime, c: Coefficients
) -> tuple[dict[int, RainInput | None], datetime | None]:
    """Chuva real por setor (ponto de previsão mais próximo), como no risco real."""
    start = current_hour(now)
    points = await forecast_points(session)
    hourly = await hourly_precipitation_by_point(
        session,
        start - timedelta(hours=c.antecedent_hours),
        start + timedelta(hours=c.window_hours),
    )
    rain = rain_inputs(hourly, start, c)
    base: dict[int, RainInput | None] = {}
    for s in sectors:
        near = nearest_point(s.latitude, s.longitude, points, c.max_point_distance_km)
        base[s.sector_id] = rain.get(near[0]) if near else None
    return base, max((p.issued_at for p in points), default=None)


def _scenario_json(
    scenario: Scenario, hybrid: Hybrid | None, uncertainty: Uncertainty | None
) -> dict[str, Any]:
    data: dict[str, Any] = scenario.as_dict()
    data["hybrid"] = None if hybrid is None else asdict(hybrid)
    data["uncertainty"] = None if uncertainty is None else asdict(uncertainty)
    return data


async def run_simulation(
    session: AsyncSession,
    scenario: Scenario,
    *,
    now: datetime,
    preset: str | None = None,
    hybrid: Hybrid | None = None,
    uncertainty: Uncertainty | None = None,
    seed: int | None = None,
    repeat_of: uuid.UUID | None = None,
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> SimulationRun:
    started = time.perf_counter()
    sectors = await load_sectors(session, now, c)
    if not sectors:
        raise SimulationUnavailableError(
            "Nenhum setor de risco sincronizado do GeoSampa: não há o que simular."
        )
    if uncertainty is not None and uncertainty.members > 1 and seed is None:
        seed = secrets.randbelow(2**31)  # sorteado e gravado (FR-108)
    base: dict[int, RainInput | None] | None = None
    issued_at: datetime | None = None
    if hybrid is not None:
        freshness = await source_freshness(session, FORECAST_SOURCE, now)
        if freshness in UNKNOWN_FRESHNESS:
            raise HybridUnavailableError(
                f"Previsão {FRESHNESS_LABELS.get(freshness, freshness.lower())}: o modo a partir "
                "da previsão real precisa da previsão atual. A simulação só com o cenário "
                "continua disponível."
            )
        base, issued_at = await _forecast_base(session, sectors, now, c)
    result = simulate(
        sectors,
        scenario,
        now=now,
        c=c,
        hybrid=hybrid,
        base=base,
        uncertainty=uncertainty,
        seed=seed,
    )
    real_run, real = await _real_categories(session)
    comparison = compare(result, real, await _subprefectures(session))
    comparison["real_run"] = (
        None
        if real_run is None
        else {
            "id": real_run.id,
            "computed_at": real_run.computed_at.isoformat(),
            "stale": now - real_run.computed_at > timedelta(hours=c.stale_after_hours),
        }
    )
    run_id = uuid.uuid4()
    duration_ms = round((time.perf_counter() - started) * 1000)
    await session.execute(
        insert(simulation_runs).values(
            id=run_id,
            created_at=now,
            kind="SIMULATED",
            mode="HYBRID" if hybrid is not None else "SIMULATION",
            scenario=_scenario_json(scenario, hybrid, uncertainty),
            preset=preset,
            seed=seed,
            members=uncertainty.members if uncertainty is not None else 1,
            simulation_engine_version=result.engine_version,
            risk_engine_version=result.risk_engine_version,
            sectors_fingerprint=result.fingerprint,
            sector_count=len(result.outcomes),
            forecast_issued_at=issued_at,
            counts=result.counts,
            comparison=comparison,
            duration_ms=duration_ms,
            ensemble=None if result.ensemble is None else asdict(result.ensemble),
            repeat_of=repeat_of,
        )
    )
    rows = [
        {
            "run_id": run_id,
            "sector_id": o.assessment.sector_id,
            "category": o.assessment.category.value,
            "p_high": o.p_high,
            "p_critical": o.p_critical,
            "rain_level": o.assessment.rain_level,
            "susceptibility": o.assessment.susceptibility,
            "p1h_max_mm": o.assessment.p1h_max,
            "p24_mm": o.assessment.p24,
            "a72_mm": o.assessment.a72,
            "rain_factor": o.rain_factor,
            "distance_km": o.distance_km,
            "factors": [f.as_dict() for f in o.assessment.factors],
        }
        for o in result.outcomes
    ]
    for i in range(0, len(rows), 500):
        await session.execute(insert(simulation_results), rows[i : i + 500])
    await purge_old_runs(session, now)
    await session.commit()
    logger.info("simulation_run", run_id=str(run_id), ms=duration_ms, seed=seed, **result.counts)
    found = await get_run(session, run_id, now=now, c=c)
    if found is None:  # acabou de ser gravada; só some se a retenção a apagar
        raise SimulationUnavailableError("A simulação gravada não foi encontrada.")
    return found


async def _results(session: AsyncSession, run_id: uuid.UUID) -> dict[int, tuple[Any, ...]]:
    r = simulation_results
    rows = await session.execute(
        select(r.c.sector_id, r.c.category, r.c.p_high, r.c.p_critical).where(r.c.run_id == run_id)
    )
    return {int(row[0]): tuple(row[1:]) for row in rows.tuples()}


async def _repeat_check(session: AsyncSession, row: Any) -> RepeatCheck | None:
    if row.repeat_of is None:
        return None
    original = (
        await session.execute(select(simulation_runs).where(simulation_runs.c.id == row.repeat_of))
    ).one_or_none()
    if original is None:
        return None
    return RepeatCheck(
        original_id=original.id,
        same_engine_versions=(
            original.simulation_engine_version == row.simulation_engine_version
            and original.risk_engine_version == row.risk_engine_version
        ),
        same_sectors=original.sectors_fingerprint == row.sectors_fingerprint,
        same_forecast=None
        if row.mode != "HYBRID"
        else original.forecast_issued_at == row.forecast_issued_at,
        identical_results=await _results(session, original.id) == await _results(session, row.id),
    )


async def get_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    now: datetime,
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> SimulationRun | None:
    row = (
        await session.execute(select(simulation_runs).where(simulation_runs.c.id == run_id))
    ).one_or_none()
    if row is None:
        return None
    current = await load_sectors(session, now, c)
    banner = HYBRID_BANNER if row.mode == "HYBRID" else BANNER
    return SimulationRun.model_validate(
        {
            **row._mapping,
            "scenario_text": scenario_text(row.scenario),
            "sectors_changed": bool(current)
            and sectors_fingerprint(current) != row.sectors_fingerprint,
            "repeat_check": await _repeat_check(session, row),
            "banner": banner,
        }
    )


async def list_runs(session: AsyncSession, limit: int) -> list[RunListItem]:
    r = simulation_runs
    rows = await session.execute(select(r).order_by(r.c.created_at.desc(), r.c.id).limit(limit))
    return [
        RunListItem(
            id=row.id,
            created_at=row.created_at,
            mode=row.mode,
            scenario_text=scenario_text(row.scenario),
            preset=row.preset,
            seed=row.seed,
            members=row.members,
            high_or_above=int(row.counts.get("HIGH", 0)) + int(row.counts.get("CRITICAL", 0)),
            unknown=int(row.counts.get("UNKNOWN", 0)),
        )
        for row in rows
    ]


def _sector_columns() -> list[Any]:
    s, r = hydro_risk_sectors, simulation_results
    return [
        s.c.id,
        s.c.source_code.label("code"),
        s.c.area_name.label("name"),
        s.c.subprefecture,
        s.c.grade,
        s.c.households,
        r.c.category,
        r.c.rain_level,
        r.c.susceptibility,
        r.c.p1h_max_mm,
        r.c.p24_mm,
        r.c.a72_mm,
        r.c.rain_factor,
        r.c.distance_km,
        r.c.p_high,
        r.c.p_critical,
        r.c.factors,
    ]


def _sim_rank() -> Any:
    r = simulation_results
    return case(*((r.c.category == k, v) for k, v in CATEGORY_RANK.items()), else_=0)


async def list_sectors(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    category: str | None,
    subprefecture: str | None,
    limit: int,
    offset: int,
) -> tuple[list[SimulatedSector], int]:
    s, r = hydro_risk_sectors, simulation_results
    conditions = [r.c.run_id == run_id]
    if category:
        conditions.append(r.c.category == category)
    if subprefecture:
        conditions.append(s.c.subprefecture == subprefecture)
    base = select(*_sector_columns()).join(r, r.c.sector_id == s.c.id).where(*conditions)
    total = int(
        (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    )
    rows = list(
        await session.execute(
            base.order_by(
                _sim_rank().desc(),
                r.c.p_high.desc().nulls_last(),
                r.c.rain_level.desc().nulls_last(),
                r.c.susceptibility.desc(),
                s.c.households.desc().nulls_last(),
                s.c.source_code,
            )
            .limit(limit)
            .offset(offset)
        )
    )
    real = await _real_for(session, [int(row.id) for row in rows])
    return [_sector(row, real.get(int(row.id))) for row in rows], total


async def _real_for(session: AsyncSession, ids: Sequence[int]) -> dict[int, str]:
    run = await latest_run(session)
    if run is None or not ids:
        return {}
    a = risk_assessments
    rows = await session.execute(
        select(a.c.sector_id, a.c.category).where(a.c.run_id == run.id, a.c.sector_id.in_(ids))
    )
    return {int(i): cat for i, cat in rows.tuples()}


def _sector(row: Any, real_category: str | None) -> SimulatedSector:
    return SimulatedSector.model_validate({**row._mapping, "real_category": real_category})


async def sector_detail(
    session: AsyncSession, run_id: uuid.UUID, sector_id: int
) -> SimulatedSector | None:
    s, r = hydro_risk_sectors, simulation_results
    row = (
        await session.execute(
            select(*_sector_columns())
            .join(r, r.c.sector_id == s.c.id)
            .where(r.c.run_id == run_id, s.c.id == sector_id)
        )
    ).one_or_none()
    if row is None:
        return None
    real = await _real_for(session, [sector_id])
    return _sector(row, real.get(sector_id))


async def simulation_features(session: AsyncSession, run_id: uuid.UUID) -> list[dict[str, Any]]:
    """Polígonos simplificados com a categoria simulada (`kind = SIMULATED`)."""
    s, r = hydro_risk_sectors, simulation_results
    simplified = func.ST_Multi(func.ST_SimplifyPreserveTopology(s.c.geom, SIMPLIFY_TOLERANCE_DEG))
    rows = await session.execute(
        select(
            s.c.id,
            s.c.source_code,
            s.c.area_name,
            s.c.subprefecture,
            s.c.grade,
            r.c.category,
            r.c.rain_level,
            r.c.p1h_max_mm,
            r.c.p24_mm,
            r.c.p_high,
            simulation_runs.c.mode,
            func.ST_AsGeoJSON(simplified, 6).label("geometry"),
        )
        .join(r, r.c.sector_id == s.c.id)
        .join(simulation_runs, simulation_runs.c.id == r.c.run_id)
        .where(r.c.run_id == run_id)
        .order_by(s.c.id)
    )
    return [
        {
            "type": "Feature",
            "id": row.id,
            "geometry": json.loads(row.geometry),
            "properties": {
                "id": row.id,
                "code": row.source_code,
                "name": row.area_name,
                "subprefecture": row.subprefecture,
                "grade": row.grade,
                "category": row.category,
                "rain_level": row.rain_level,
                "p1h_max_mm": row.p1h_max_mm,
                "p24_mm": row.p24_mm,
                "p_high": row.p_high,
                "kind": "SIMULATED",
                "mode": row.mode,
            },
        }
        for row in rows
    ]


class Center(BaseModel):
    name: str
    latitude: float
    longitude: float
    sectors: int


async def subprefecture_centers(session: AsyncSession) -> list[Center]:
    """Centro de cada subprefeitura, a partir dos setores dela (escolha sem mapa, NFR-103)."""
    s = hydro_risk_sectors
    point = func.ST_PointOnSurface(func.ST_Collect(s.c.geom))
    rows = await session.execute(
        select(
            s.c.subprefecture,
            func.ST_Y(point).label("latitude"),
            func.ST_X(point).label("longitude"),
            func.count().label("sectors"),
        )
        .where(s.c.active.is_(True), s.c.subprefecture.is_not(None))
        .group_by(s.c.subprefecture)
        .order_by(s.c.subprefecture)
    )
    return [
        Center(
            name=r.subprefecture,
            latitude=round(float(r.latitude), 5),
            longitude=round(float(r.longitude), 5),
            sectors=int(r.sectors),
        )
        for r in rows
    ]


def presets() -> list[PresetOut]:
    return [
        PresetOut(
            code=p.code,
            name=p.name,
            description=p.description,
            origin=p.origin,
            scenario=p.scenario.as_dict(),
        )
        for p in PRESETS
    ]

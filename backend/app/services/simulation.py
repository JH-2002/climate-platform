"""Laboratório de simulação (spec 007): monta os setores, roda o motor, compara e grava.

Os resultados ficam em `simulation_runs` e `simulation_results` e nunca entram nas tabelas,
telas ou indicadores do risco real (BR-101).
"""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    hydro_risk_sectors,
    risk_assessments,
    simulation_results,
    simulation_runs,
)
from app.risk.coefficients import DEFAULT_COEFFICIENTS, Category, Coefficients
from app.services.risk import (
    CATEGORY_RANK,
    SIMPLIFY_TOLERANCE_DEG,
    latest_run,
    sector_rows,
)
from app.simulation.engine import SimSector, SimulationResult, sectors_fingerprint, simulate
from app.simulation.scenario import PATTERN_LABELS, PRESETS, Pattern, Scenario

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
    factors: list[Factor]


# --- funções puras ---------------------------------------------------------------------------


def scenario_text(scenario: Mapping[str, Any]) -> str:
    """Resumo legível do cenário, usado no histórico e no topo do resultado."""
    pattern = PATTERN_LABELS[Pattern(scenario["pattern"])]
    hours = "1 hora" if scenario["duration_h"] == 1 else f"{scenario['duration_h']} horas"
    total = f"{scenario['total_mm']:g}".replace(".", ",")
    where = "na cidade inteira"
    cell = scenario.get("cell")
    if cell:
        where = f"numa célula de {cell['radius_km']:g} km".replace(".", ",")
    antecedent = f"{scenario['antecedent_mm']:g}".replace(".", ",")
    return f"{total} mm em {hours}, {pattern}, {where}; {antecedent} mm nas 72 h anteriores"


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


async def _enforce_retention(session: AsyncSession, now: datetime) -> None:
    """NFR-102: 30 dias e no máximo 500 execuções; as mais antigas saem primeiro."""
    r = simulation_runs
    await session.execute(delete(r).where(r.c.created_at < now - timedelta(days=RETENTION_DAYS)))
    keep = select(r.c.id).order_by(r.c.created_at.desc()).limit(MAX_STORED_RUNS)
    await session.execute(delete(r).where(r.c.id.not_in(keep.scalar_subquery())))


async def run_simulation(
    session: AsyncSession,
    scenario: Scenario,
    *,
    now: datetime,
    preset: str | None = None,
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> SimulationRun:
    started = time.perf_counter()
    sectors = await load_sectors(session, now, c)
    if not sectors:
        raise SimulationUnavailableError(
            "Nenhum setor de risco sincronizado do GeoSampa: não há o que simular."
        )
    result = simulate(sectors, scenario, now=now, c=c)
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
            mode="SIMULATION",
            scenario=scenario.as_dict(),
            preset=preset,
            seed=None,
            members=1,
            simulation_engine_version=result.engine_version,
            risk_engine_version=result.risk_engine_version,
            sectors_fingerprint=result.fingerprint,
            sector_count=len(result.outcomes),
            forecast_issued_at=None,
            counts=result.counts,
            comparison=comparison,
            duration_ms=duration_ms,
        )
    )
    rows = [
        {
            "run_id": run_id,
            "sector_id": o.assessment.sector_id,
            "category": o.assessment.category.value,
            "p_high": None,
            "p_critical": None,
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
    await _enforce_retention(session, now)
    await session.commit()
    logger.info("simulation_run", run_id=str(run_id), ms=duration_ms, **result.counts)
    found = await get_run(session, run_id, now=now, c=c)
    if found is None:  # acabou de ser gravada; só some se a retenção a apagar
        raise SimulationUnavailableError("A simulação gravada não foi encontrada.")
    return found


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
    return SimulationRun.model_validate(
        {
            **row._mapping,
            "scenario_text": scenario_text(row.scenario),
            "sectors_changed": bool(current)
            and sectors_fingerprint(current) != row.sectors_fingerprint,
        }
    )


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
            func.ST_AsGeoJSON(simplified, 6).label("geometry"),
        )
        .join(r, r.c.sector_id == s.c.id)
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
                "kind": "SIMULATED",
                "mode": "SIMULATION",
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

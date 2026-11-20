"""Motor de simulação (FR-102, NFR-100): gera a chuva do cenário e chama o motor de risco.

Nenhuma regra de risco é copiada aqui. Cada setor recebe a própria chave de "ponto" (`s:<id>`)
para que a chuva seja calculada na resolução de setor (ADR-012).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from app.risk.coefficients import DEFAULT_COEFFICIENTS, Category, Coefficients
from app.risk.engine import Assessment, RainInput, RunResult, SectorInput, assess
from app.risk.rules import Factor, category, rain_level
from app.simulation.ensemble import EnsembleSummary, apply_member, draw_members, summarize
from app.simulation.rain import cell_factor, combine, scenario_rain
from app.simulation.scenario import Hybrid, Scenario, ScenarioError, Uncertainty, validate

SIMULATION_ENGINE_VERSION = "0.1.0-experimental"
# Em simulação não há falta de dado nem previsão vencida (BR-103).
SIMULATED_FRESHNESS = "FRESH"

# Os textos do motor de risco falam de previsão; na simulação a chuva vem do cenário.
_RELABEL = (
    ("prevista nas próximas 24 h", "no cenário"),
    ("prevista (", "no cenário ("),
    ("Chuva estimada nas 72 h anteriores", "Chuva das 72 h anteriores no cenário"),
)


@dataclass(frozen=True)
class SimSector:
    sector_id: int
    grade: int
    in_flood_extent: bool
    nearby_occurrences: int
    latitude: float
    longitude: float


@dataclass(frozen=True)
class SectorOutcome:
    assessment: Assessment
    rain_factor: float
    distance_km: float | None
    # Probabilidades entre as variações (None sem variações ou com categoria desconhecida).
    p_high: float | None = None
    p_critical: float | None = None


@dataclass(frozen=True)
class SimulationResult:
    engine_version: str
    risk_engine_version: str
    fingerprint: str
    outcomes: tuple[SectorOutcome, ...]
    counts: dict[str, int]
    ensemble: EnsembleSummary | None = None


def sectors_fingerprint(sectors: Iterable[SimSector]) -> str:
    """Impressão digital dos dados de setor que entram no cálculo (BR-102)."""
    digest = hashlib.sha256()
    for s in sorted(sectors, key=lambda s: s.sector_id):
        digest.update(
            f"{s.sector_id}|{s.grade}|{int(s.in_flood_extent)}|{s.nearby_occurrences}\n".encode()
        )
    return digest.hexdigest()


def relabel(factor: Factor) -> Factor:
    text = factor.text
    for old, new in _RELABEL:
        text = text.replace(old, new)
    return replace(factor, text=text)


def _point_key(sector_id: int) -> str:
    return f"s:{sector_id}"


def _sector_rain(
    sector: SimSector,
    scenario: Scenario,
    hybrid: Hybrid | None,
    base: Mapping[int, RainInput | None] | None,
) -> tuple[RainInput | None, float, float | None]:
    """Chuva do setor: cenário puro (SIMULATION) ou previsão real ajustada (HYBRID)."""
    factor, distance = cell_factor(scenario.cell, sector.latitude, sector.longitude)
    if hybrid is None:
        return scenario_rain(scenario, factor), factor, distance
    real = base.get(sector.sector_id) if base is not None else None
    if real is None:
        return None, factor, distance  # sem previsão para o setor: desconhecido (BR-103)
    storm = scenario_rain(scenario, factor) if hybrid.add_storm else None
    return combine(real, storm, hybrid.multiplier), factor, distance


def simulate(
    sectors: Sequence[SimSector],
    scenario: Scenario,
    *,
    now: datetime,
    c: Coefficients = DEFAULT_COEFFICIENTS,
    hybrid: Hybrid | None = None,
    base: Mapping[int, RainInput | None] | None = None,
    uncertainty: Uncertainty | None = None,
    seed: int | None = None,
) -> SimulationResult:
    """Cenário central avaliado pelo motor de risco; variações opcionais com seed.

    O cenário central dá a categoria e a explicação de cada setor. As variações só contam
    quantas vezes cada setor chega a alto ou crítico, com as mesmas regras do motor.
    """
    validate(scenario, hybrid=hybrid, uncertainty=uncertainty, seed=seed)
    inputs: list[SectorInput] = []
    rain: dict[str, RainInput] = {}
    spatial: dict[int, tuple[float, float | None]] = {}
    for s in sectors:
        sector_rain, factor, distance = _sector_rain(s, scenario, hybrid, base)
        spatial[s.sector_id] = (factor, distance)
        key = _point_key(s.sector_id) if sector_rain is not None else None
        if key is not None and sector_rain is not None:
            rain[key] = sector_rain
        inputs.append(
            SectorInput(
                sector_id=s.sector_id,
                grade=s.grade,
                in_flood_extent=s.in_flood_extent,
                nearby_occurrences=s.nearby_occurrences,
                point_key=key,
                point_distance_km=0.0 if key else None,
            )
        )
    run: RunResult = assess(inputs, rain, freshness=SIMULATED_FRESHNESS, now=now, c=c)

    probabilities: dict[int, tuple[float, float]] = {}
    summary: EnsembleSummary | None = None
    if uncertainty is not None and uncertainty.members > 1:
        if seed is None:
            raise ScenarioError("Variações precisam de um seed")
        probabilities, summary = _ensemble(
            sectors, run, scenario, hybrid, base, uncertainty, seed, c
        )

    outcomes = tuple(
        SectorOutcome(
            assessment=replace(a, factors=tuple(relabel(f) for f in a.factors), point_key=None),
            rain_factor=round(spatial[a.sector_id][0], 3),
            distance_km=None
            if spatial[a.sector_id][1] is None
            else round(spatial[a.sector_id][1] or 0.0, 2),
            p_high=probabilities.get(a.sector_id, (None, None))[0],
            p_critical=probabilities.get(a.sector_id, (None, None))[1],
        )
        for a in run.assessments
    )
    return SimulationResult(
        engine_version=SIMULATION_ENGINE_VERSION,
        risk_engine_version=run.engine_version,
        fingerprint=sectors_fingerprint(sectors),
        outcomes=outcomes,
        counts=dict(run.counts),
        ensemble=summary,
    )


def _ensemble(
    sectors: Sequence[SimSector],
    central: RunResult,
    scenario: Scenario,
    hybrid: Hybrid | None,
    base: Mapping[int, RainInput | None] | None,
    uncertainty: Uncertainty,
    seed: int,
    c: Coefficients,
) -> tuple[dict[int, tuple[float, float]], EnsembleSummary]:
    by_id = {a.sector_id: a for a in central.assessments}
    # Suscetibilidade não depende da chuva: vem da avaliação central.
    known = [s for s in sectors if by_id[s.sector_id].category is not Category.UNKNOWN]
    high = dict.fromkeys((s.sector_id for s in known), 0)
    critical = dict.fromkeys((s.sector_id for s in known), 0)
    high_counts: list[int] = []
    for member in draw_members(seed, uncertainty):
        varied, varied_hybrid = apply_member(member, scenario, hybrid)
        total_high = 0
        for s in known:
            sector_rain, _, _ = _sector_rain(s, varied, varied_hybrid, base)
            if sector_rain is None:
                continue
            level = rain_level(sector_rain.p1h_max, sector_rain.p24, sector_rain.a72, c)
            cat = category(level, by_id[s.sector_id].susceptibility)
            if cat in (Category.HIGH, Category.CRITICAL):
                high[s.sector_id] += 1
                total_high += 1
            if cat is Category.CRITICAL:
                critical[s.sector_id] += 1
        high_counts.append(total_high)
    n = uncertainty.members
    probabilities = {sid: (round(high[sid] / n, 3), round(critical[sid] / n, 3)) for sid in high}
    return probabilities, summarize(high_counts)

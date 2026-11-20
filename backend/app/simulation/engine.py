"""Motor de simulação (FR-102, NFR-100): gera a chuva do cenário e chama o motor de risco.

Nenhuma regra de risco é copiada aqui. Cada setor recebe a própria chave de "ponto" (`s:<id>`)
para que a chuva seja calculada na resolução de setor (ADR-012).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from app.risk.coefficients import DEFAULT_COEFFICIENTS, Coefficients
from app.risk.engine import Assessment, RunResult, SectorInput, assess
from app.risk.rules import Factor
from app.simulation.rain import cell_factor, scenario_rain
from app.simulation.scenario import Scenario, validate

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


@dataclass(frozen=True)
class SimulationResult:
    engine_version: str
    risk_engine_version: str
    fingerprint: str
    outcomes: tuple[SectorOutcome, ...]
    counts: dict[str, int]


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


def simulate(
    sectors: Sequence[SimSector],
    scenario: Scenario,
    *,
    now: datetime,
    c: Coefficients = DEFAULT_COEFFICIENTS,
) -> SimulationResult:
    validate(scenario)
    inputs: list[SectorInput] = []
    rain = {}
    spatial: dict[int, tuple[float, float | None]] = {}
    for s in sectors:
        key = _point_key(s.sector_id)
        factor, distance = cell_factor(scenario.cell, s.latitude, s.longitude)
        spatial[s.sector_id] = (factor, distance)
        rain[key] = scenario_rain(scenario, factor)
        inputs.append(
            SectorInput(
                sector_id=s.sector_id,
                grade=s.grade,
                in_flood_extent=s.in_flood_extent,
                nearby_occurrences=s.nearby_occurrences,
                point_key=key,
                point_distance_km=0.0,
            )
        )
    run: RunResult = assess(inputs, rain, freshness=SIMULATED_FRESHNESS, now=now, c=c)
    outcomes = tuple(
        SectorOutcome(
            assessment=replace(a, factors=tuple(relabel(f) for f in a.factors), point_key=None),
            rain_factor=round(spatial[a.sector_id][0], 3),
            distance_km=None
            if spatial[a.sector_id][1] is None
            else round(spatial[a.sector_id][1] or 0.0, 2),
        )
        for a in run.assessments
    )
    return SimulationResult(
        engine_version=SIMULATION_ENGINE_VERSION,
        risk_engine_version=run.engine_version,
        fingerprint=sectors_fingerprint(sectors),
        outcomes=outcomes,
        counts=dict(run.counts),
    )

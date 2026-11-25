"""Variações com seed (FR-108, NFR-100). Puro e determinístico para o mesmo seed.

Cada variação sorteia, nesta ordem fixa: o fator de intensidade, o ângulo e a distância do
deslocamento (distância × √u, para cobrir o disco por igual). Mudar a ordem muda os
resultados gravados: os testes fixam valores de referência para o seed 42.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from app.simulation.scenario import Cell, Hybrid, Scenario, Uncertainty

KM_PER_DEGREE_LAT = 111.32


@dataclass(frozen=True)
class Member:
    factor: float
    north_km: float
    east_km: float


@dataclass(frozen=True)
class EnsembleSummary:
    members: int
    mean: float
    p10: float
    p90: float
    minimum: int
    maximum: int


def draw_members(seed: int, uncertainty: Uncertainty) -> tuple[Member, ...]:
    rng = random.Random(seed)  # noqa: S311 — reprodutibilidade, não criptografia
    u = uncertainty.intensity_pct / 100
    members = []
    for _ in range(uncertainty.members):
        factor = 1 + rng.uniform(-u, u)
        angle = rng.uniform(0, 2 * math.pi)
        distance = uncertainty.shift_km * math.sqrt(rng.random())
        members.append(
            Member(
                factor=factor,
                north_km=distance * math.cos(angle),
                east_km=distance * math.sin(angle),
            )
        )
    return tuple(members)


def shift_cell(cell: Cell, north_km: float, east_km: float) -> Cell:
    lat = cell.latitude + north_km / KM_PER_DEGREE_LAT
    lon = cell.longitude + east_km / (KM_PER_DEGREE_LAT * math.cos(math.radians(cell.latitude)))
    return replace(cell, latitude=lat, longitude=lon)


def apply_member(
    member: Member, scenario: Scenario, hybrid: Hybrid | None
) -> tuple[Scenario, Hybrid | None]:
    """A intensidade vale para toda a chuva: a do cenário e a previsão multiplicada."""
    cell = (
        None
        if scenario.cell is None
        else shift_cell(scenario.cell, member.north_km, member.east_km)
    )
    varied = replace(scenario, total_mm=scenario.total_mm * member.factor, cell=cell)
    if hybrid is None:
        return varied, None
    return varied, replace(hybrid, multiplier=hybrid.multiplier * member.factor)


def _quantile(sorted_values: list[int], q: float) -> float:
    """Interpolação linear entre postos (mesmo método do `numpy.percentile` padrão)."""
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    low = math.floor(pos)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def summarize(high_counts: list[int]) -> EnsembleSummary:
    values = sorted(high_counts)
    return EnsembleSummary(
        members=len(values),
        mean=round(sum(values) / len(values), 1),
        p10=round(_quantile(values, 0.1), 1),
        p90=round(_quantile(values, 0.9), 1),
        minimum=values[0],
        maximum=values[-1],
    )

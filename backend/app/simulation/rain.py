"""Chuva por setor a partir do cenário (FR-101). Puro."""

from __future__ import annotations

from app.risk.engine import RainInput
from app.risk.geo import haversine_km
from app.simulation.scenario import PEAK_SHARE, Cell, Scenario

FULL_WINDOW_HOURS = 24


def peak_hour_mm(total_mm: float, duration_h: int, share: float) -> float:
    """Chuva da hora mais forte. Nunca abaixo da média horária nem acima do total."""
    if duration_h <= 1:
        return total_mm
    return min(total_mm, max(total_mm / duration_h, share * total_mm))


def spatial_factor(distance_km: float, radius_km: float) -> float:
    """1 até o raio; cai em linha reta até 0 em duas vezes o raio."""
    if distance_km <= radius_km:
        return 1.0
    if distance_km >= 2 * radius_km:
        return 0.0
    return (2 * radius_km - distance_km) / radius_km


def cell_factor(cell: Cell | None, latitude: float, longitude: float) -> tuple[float, float | None]:
    """Fator espacial e distância ao centro (None para a cidade inteira)."""
    if cell is None:
        return 1.0, None
    d = haversine_km(latitude, longitude, cell.latitude, cell.longitude)
    return spatial_factor(d, cell.radius_km), d


def scenario_rain(scenario: Scenario, factor: float) -> RainInput:
    """A chuva antecedente descreve o estado do solo na cidade: não é escalada pela célula."""
    peak = peak_hour_mm(scenario.total_mm, scenario.duration_h, PEAK_SHARE[scenario.pattern])
    return RainInput(
        p1h_max=round(peak * factor, 2),
        p24=round(scenario.total_mm * factor, 2),
        hours_available=FULL_WINDOW_HOURS,
        a72=scenario.antecedent_mm,
    )


def combine(base: RainInput, storm: RainInput | None, multiplier: float) -> RainInput:
    """HYBRID: previsão real × multiplicador, somada à chuva do cenário (se houver).

    Somar as horas de pico supõe que o temporal do cenário cai na hora mais chuvosa da
    previsão: é o caso mais desfavorável, dito na tela.
    """
    p1h = None if base.p1h_max is None else base.p1h_max * multiplier
    p24 = base.p24 * multiplier
    if storm is not None:
        p1h = (p1h or 0.0) + (storm.p1h_max or 0.0)
        p24 += storm.p24
    return RainInput(
        p1h_max=None if p1h is None else round(p1h, 2),
        p24=round(p24, 2),
        hours_available=base.hours_available,
        a72=base.a72,
    )

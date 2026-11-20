"""Motor de simulação (spec 007, Parte A): cenário, chuva por setor e avaliação."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.risk.geo import haversine_km
from app.risk.rules import Factor
from app.simulation.engine import SimSector, relabel, sectors_fingerprint, simulate
from app.simulation.rain import peak_hour_mm, scenario_rain, spatial_factor
from app.simulation.scenario import (
    PRESETS,
    Cell,
    Pattern,
    Scenario,
    ScenarioError,
    validate,
)

NOW = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
CENTER = (-23.5505, -46.6333)
# ~20 km ao norte do centro.
FAR = (-23.3707, -46.6333)


def sector(sector_id: int, grade: int, lat: float, lon: float, **kw: object) -> SimSector:
    return SimSector(
        sector_id=sector_id,
        grade=grade,
        in_flood_extent=bool(kw.get("flood", False)),
        nearby_occurrences=int(kw.get("occ", 0)),  # type: ignore[call-overload]
        latitude=lat,
        longitude=lon,
    )


SECTORS = [sector(1, 4, *CENTER), sector(2, 4, *FAR), sector(3, 2, *CENTER)]


def cell_scenario(total: float, radius: float = 6.0) -> Scenario:
    return Scenario(total, 1, Pattern.CONSTANT, 0.0, Cell(*CENTER, radius))


def categories(result: object) -> dict[int, str]:
    return {o.assessment.sector_id: o.assessment.category.value for o in result.outcomes}  # type: ignore[attr-defined]


def test_far_point_is_about_20_km_away() -> None:
    assert haversine_km(*CENTER, *FAR) == pytest.approx(20.0, abs=0.1)


@pytest.mark.parametrize(
    ("total", "duration", "pattern", "expected"),
    [
        (40.0, 1, Pattern.CONSTANT, 40.0),
        (80.0, 12, Pattern.CONSTANT, 80.0 / 12),
        (100.0, 24, Pattern.PEAKED, 50.0),
        (100.0, 24, Pattern.SHARP, 70.0),
        (30.0, 2, Pattern.PEAKED, 15.0),
    ],
)
def test_peak_hour(total: float, duration: int, pattern: Pattern, expected: float) -> None:
    from app.simulation.scenario import PEAK_SHARE

    assert peak_hour_mm(total, duration, PEAK_SHARE[pattern]) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("distance", "expected"), [(0, 1.0), (6, 1.0), (9, 0.5), (12, 0.0), (20, 0.0)]
)
def test_spatial_factor_edges(distance: float, expected: float) -> None:
    assert spatial_factor(distance, 6.0) == pytest.approx(expected)


def test_antecedent_is_not_scaled_by_cell() -> None:
    rain = scenario_rain(Scenario(40.0, 1, Pattern.CONSTANT, 80.0), 0.5)
    assert (rain.p1h_max, rain.p24, rain.a72, rain.hours_available) == (20.0, 20.0, 80.0, 24)


def test_ac100_storm_over_r4_sector() -> None:
    """AC-100: 40 mm/h → alto; 60 mm/h → crítico; setor a 20 km fica baixo."""
    forte = categories(simulate(SECTORS, cell_scenario(40.0), now=NOW))
    assert forte[1] == "HIGH" and forte[2] == "LOW"
    muito_forte = categories(simulate(SECTORS, cell_scenario(60.0), now=NOW))
    assert muito_forte[1] == "CRITICAL" and muito_forte[2] == "LOW"


def test_ac101_same_scenario_same_result() -> None:
    scenario = Scenario(136.0, 24, Pattern.PEAKED, 20.0)
    assert simulate(SECTORS, scenario, now=NOW) == simulate(SECTORS, scenario, now=NOW)


def test_simulation_never_unknown_and_counts_add_up() -> None:
    result = simulate(SECTORS, Scenario(5.0, 6, Pattern.CONSTANT, 0.0), now=NOW)
    assert result.counts["UNKNOWN"] == 0
    assert sum(result.counts.values()) == len(SECTORS)


def test_factors_speak_of_scenario_not_forecast() -> None:
    result = simulate(SECTORS, cell_scenario(60.0), now=NOW)
    texts = [f.text for o in result.outcomes for f in o.assessment.factors]
    assert not any("prevista" in t for t in texts)
    assert any("no cenário" in t for t in texts)
    assert relabel(Factor("RAIN_P1H", "Chuva forte prevista (30 mm em 1 h)", "raises")).text == (
        "Chuva forte no cenário (30 mm em 1 h)"
    )


def test_outcome_reports_distance_and_factor() -> None:
    result = simulate(SECTORS, cell_scenario(40.0), now=NOW)
    far = next(o for o in result.outcomes if o.assessment.sector_id == 2)
    assert far.rain_factor == 0.0 and far.distance_km == pytest.approx(20.0, abs=0.1)
    citywide = simulate(SECTORS, Scenario(40.0, 1, Pattern.CONSTANT, 0.0), now=NOW)
    assert all(o.distance_km is None and o.rain_factor == 1.0 for o in citywide.outcomes)


def test_fingerprint_changes_with_sector_data() -> None:
    base = sectors_fingerprint(SECTORS)
    assert base == sectors_fingerprint(list(reversed(SECTORS)))
    changed = [sector(1, 3, *CENTER), *SECTORS[1:]]
    assert sectors_fingerprint(changed) != base


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        (Scenario(400.0, 1, Pattern.CONSTANT, 0.0), "Chuva total"),
        (Scenario(0.0, 1, Pattern.CONSTANT, 0.0), "Chuva total"),
        (Scenario(10.0, 25, Pattern.CONSTANT, 0.0), "Duração"),
        (Scenario(10.0, 1, Pattern.CONSTANT, 301.0), "72 h"),
        (Scenario(10.0, 1, Pattern.CONSTANT, 0.0, Cell(*CENTER, 1.0)), "Raio"),
        (Scenario(10.0, 1, Pattern.CONSTANT, 0.0, Cell(-22.9, -43.2, 5.0)), "Latitude"),
    ],
)
def test_limits(scenario: Scenario, message: str) -> None:
    with pytest.raises(ScenarioError, match=message):
        validate(scenario)


def test_presets_are_valid() -> None:
    assert len({p.code for p in PRESETS}) == len(PRESETS)
    for preset in PRESETS:
        validate(preset.scenario)
        assert preset.origin

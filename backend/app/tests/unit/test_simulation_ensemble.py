"""Spec 007, Parte B — variações com seed e modo HYBRID (motor puro)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.risk.engine import RainInput
from app.risk.geo import haversine_km
from app.simulation.engine import SimSector, simulate
from app.simulation.ensemble import draw_members, shift_cell, summarize
from app.simulation.rain import combine
from app.simulation.scenario import Cell, Hybrid, Pattern, Scenario, ScenarioError, Uncertainty

NOW = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
CENTER = (-23.5505, -46.6333)
# Setores R4 a 0, 7, 10 e 14 km ao norte do centro.
SECTORS = [
    SimSector(i, 4, False, 0, CENTER[0] + km / 111.32, CENTER[1])
    for i, km in enumerate((0.0, 7.0, 10.0, 14.0), start=1)
]
STORM = Scenario(60.0, 1, Pattern.CONSTANT, 0.0, Cell(*CENTER, 6.0))
UNC = Uncertainty(members=100, intensity_pct=30.0, shift_km=5.0)


def test_seed_42_reference_draws() -> None:
    """A ordem dos sorteios é parte do contrato de reprodutibilidade (BR-102)."""
    members = draw_members(42, Uncertainty(3, 30.0, 5.0))
    got = [(round(m.factor, 6), round(m.north_km, 6), round(m.east_km, 6)) for m in members]
    assert got == [
        (1.083656, 2.589851, 0.410372),
        (0.833926, -0.349207, -4.098236),
        (1.235308, 2.77515, 1.687184),
    ]


def test_draws_stay_within_limits() -> None:
    for m in draw_members(7, UNC):
        assert 0.7 <= m.factor <= 1.3
        assert (m.north_km**2 + m.east_km**2) ** 0.5 <= 5.0 + 1e-9


def test_shift_cell_moves_the_requested_distance() -> None:
    moved = shift_cell(Cell(*CENTER, 6.0), 3.0, 4.0)
    assert haversine_km(*CENTER, moved.latitude, moved.longitude) == pytest.approx(5.0, abs=0.02)


def probabilities(seed: int) -> dict[int, tuple[float | None, float | None]]:
    result = simulate(SECTORS, STORM, now=NOW, uncertainty=UNC, seed=seed)
    return {o.assessment.sector_id: (o.p_high, o.p_critical) for o in result.outcomes}


def test_ac104_same_seed_same_probabilities() -> None:
    assert probabilities(42) == probabilities(42)
    assert probabilities(42) != probabilities(43)


def test_probabilities_fall_with_distance() -> None:
    p = probabilities(42)
    # 60 mm/h ± 30%: no centro sempre alto ou crítico; crítico só quando passa de 50 mm/h
    assert p == {1: (1.0, 0.84), 2: (0.8, 0.38), 3: (0.39, 0.09), 4: (0.03, 0.0)}
    assert all(0.0 <= v <= 1.0 for pair in p.values() for v in pair if v is not None)


def test_central_category_comes_from_unperturbed_scenario() -> None:
    plain = simulate(SECTORS, STORM, now=NOW)
    varied = simulate(SECTORS, STORM, now=NOW, uncertainty=UNC, seed=42)
    assert [o.assessment for o in plain.outcomes] == [o.assessment for o in varied.outcomes]
    assert plain.ensemble is None and all(o.p_high is None for o in plain.outcomes)
    assert varied.ensemble is not None and varied.ensemble.members == 100
    assert varied.ensemble.p10 <= varied.ensemble.mean <= varied.ensemble.p90


def test_members_need_a_seed() -> None:
    with pytest.raises(ScenarioError, match="seed"):
        simulate(SECTORS, STORM, now=NOW, uncertainty=UNC)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"uncertainty": Uncertainty(120, 0, 0), "seed": 1}, "variações"),
        ({"uncertainty": Uncertainty(10, 60, 0), "seed": 1}, "intensidade"),
        ({"uncertainty": Uncertainty(10, 0, 11), "seed": 1}, "Deslocamento"),
        ({"hybrid": Hybrid(4.0), "base": {}}, "Multiplicador"),
    ],
)
def test_limits(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ScenarioError, match=message):
        simulate(SECTORS, STORM, now=NOW, **kwargs)  # type: ignore[arg-type]


def test_summary_quantiles() -> None:
    s = summarize([10, 0, 20, 30, 40])
    assert (s.mean, s.p10, s.p90, s.minimum, s.maximum) == (20.0, 4.0, 36.0, 0, 40)


# --- HYBRID -----------------------------------------------------------------------------------

REAL = RainInput(p1h_max=8.0, p24=20.0, hours_available=24, a72=55.0)


def test_combine_multiplies_forecast_and_adds_storm() -> None:
    doubled = combine(REAL, None, 2.0)
    assert (doubled.p1h_max, doubled.p24, doubled.a72) == (16.0, 40.0, 55.0)
    storm = RainInput(p1h_max=30.0, p24=30.0, hours_available=24, a72=0.0)
    both = combine(REAL, storm, 1.0)
    assert (both.p1h_max, both.p24, both.a72) == (38.0, 50.0, 55.0)


def test_hybrid_uses_real_antecedent_and_marks_missing_forecast_unknown() -> None:
    base = {1: REAL, 2: REAL, 3: None, 4: REAL}
    result = simulate(SECTORS, STORM, now=NOW, hybrid=Hybrid(2.0), base=base)
    by_id = {o.assessment.sector_id: o.assessment for o in result.outcomes}
    # 16 mm/h (moderada) + um nível pela chuva antecedente real (55 mm) = forte × R4 → alto
    assert by_id[1].category.value == "HIGH"
    assert by_id[1].a72 == 55.0
    assert by_id[3].category.value == "UNKNOWN"  # BR-103
    assert result.counts["UNKNOWN"] == 1


def test_hybrid_without_storm_ignores_storm_fields() -> None:
    """Só a previsão multiplicada: os campos da chuva do cenário não são validados."""
    odd = Scenario(0.0, 0, Pattern.CONSTANT, 999.0)
    result = simulate(
        SECTORS, odd, now=NOW, hybrid=Hybrid(1.0), base=dict.fromkeys(range(1, 5), REAL)
    )
    assert {o.assessment.p24 for o in result.outcomes} == {20.0}


def test_hybrid_ensemble_varies_the_multiplier() -> None:
    base = dict.fromkeys(
        range(1, 5), RainInput(p1h_max=22.0, p24=30.0, hours_available=24, a72=0.0)
    )
    result = simulate(
        SECTORS,
        STORM,
        now=NOW,
        hybrid=Hybrid(1.0),
        base=base,
        uncertainty=Uncertainty(50, 30.0, 0.0),
        seed=5,
    )
    # 22 mm/h é moderada (R4 → moderado); com até +30% passa de 25 (forte → alto)
    p = result.outcomes[0].p_high
    assert p is not None and 0.0 < p < 1.0


def test_hybrid_keeps_real_antecedent_wording() -> None:
    result = simulate(
        SECTORS, STORM, now=NOW, hybrid=Hybrid(1.0), base=dict.fromkeys(range(1, 5), REAL)
    )
    texts = [f.text for f in result.outcomes[0].assessment.factors]
    assert (
        "Chuva estimada nas 72 h anteriores: 55 mm (solo encharcado e galerias cheias)" in texts
        or any(t.startswith("Chuva estimada nas 72 h anteriores") for t in texts)
    )
    assert not any("anteriores no cenário" in t for t in texts)

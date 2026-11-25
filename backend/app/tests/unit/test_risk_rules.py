"""T055/T056 — regras e motor de risco v0 (BR-060 a BR-063; AC-061, AC-062, AC-063, AC-066)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.risk.coefficients import DEFAULT_COEFFICIENTS as C
from app.risk.coefficients import ENGINE_VERSION, RISK_MATRIX, Category
from app.risk.engine import RainInput, SectorInput, assess, assess_sector
from app.risk.rules import category, format_mm, level_for, rain_level, susceptibility

NOW = datetime(2026, 11, 19, 15, 20, tzinfo=UTC)


def sector(
    grade: int = 3, flood: bool = False, nearby: int = 0, key: str | None = "p"
) -> SectorInput:
    return SectorInput(
        sector_id=1,
        grade=grade,
        in_flood_extent=flood,
        nearby_occurrences=nearby,
        point_key=key,
        point_distance_km=3.2 if key else None,
    )


def rain(
    p1h: float | None = 0.0, p24: float = 0.0, hours: int = 24, a72: float | None = 0.0
) -> RainInput:
    return RainInput(p1h_max=p1h, p24=p24, hours_available=hours, a72=a72)


# --- BR-060 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), (0.0, 0), (9.9, 0), (10.0, 1), (24.9, 1), (25.0, 2), (49.9, 2), (50.0, 3), (90, 3)],
)
def test_hourly_thresholds_are_inclusive(value: float | None, expected: int) -> None:
    assert level_for(value, C.p1h_thresholds_mm) == expected


@pytest.mark.parametrize(
    ("p1h", "p24", "a72", "expected"),
    [
        (0.0, 0.0, None, 0),
        (12.0, 0.0, None, 1),  # P1h moderada
        (0.0, 65.0, None, 2),  # P24 forte
        (30.0, 35.0, None, 2),  # vale o maior entre P1h e P24
        (12.0, 0.0, 50.0, 2),  # solo encharcado sobe um nível
        (60.0, 0.0, 120.0, 3),  # teto 3
        (0.0, 0.0, 200.0, 0),  # sem chuva prevista não há gatilho, mesmo com solo encharcado
    ],
)
def test_rain_level(p1h: float, p24: float, a72: float | None, expected: int) -> None:
    assert rain_level(p1h, p24, a72, C) == expected


# --- BR-061 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("grade", "flood", "nearby", "expected"),
    [
        (1, False, 0, 1),
        (2, True, 0, 3),
        (2, False, 1, 2),  # uma ocorrência só não basta
        (2, False, 2, 3),
        (1, True, 5, 2),  # mancha e ocorrências juntas somam +1, não +2
        (4, True, 9, 4),  # teto 4
    ],
)
def test_susceptibility(grade: int, flood: bool, nearby: int, expected: int) -> None:
    assert susceptibility(grade, flood, nearby, C) == expected


def test_invalid_grade_is_rejected() -> None:
    with pytest.raises(ValueError):
        susceptibility(5, False, 0, C)


# --- BR-062 ----------------------------------------------------------------------------------

EXPECTED_MATRIX = {
    0: ["LOW", "LOW", "LOW", "LOW"],
    1: ["LOW", "LOW", "MODERATE", "MODERATE"],
    2: ["LOW", "MODERATE", "HIGH", "HIGH"],
    3: ["MODERATE", "HIGH", "CRITICAL", "CRITICAL"],
}


@pytest.mark.parametrize("level", range(4))
@pytest.mark.parametrize("susc", range(1, 5))
def test_full_matrix(level: int, susc: int) -> None:
    assert category(level, susc).value == EXPECTED_MATRIX[level][susc - 1]


def test_matrix_never_decreases() -> None:
    order = list(Category)
    for level in range(4):
        row = [order.index(c) for c in RISK_MATRIX[level]]
        assert row == sorted(row)
        if level:
            above = [order.index(c) for c in RISK_MATRIX[level - 1]]
            assert all(a <= b for a, b in zip(above, row, strict=True))


# --- acceptance criteria ---------------------------------------------------------------------


def test_ac061_r3_with_strong_hourly_rain_is_high() -> None:
    result = assess_sector(sector(grade=3), rain(p1h=30.0, p24=32.0), "FRESH")
    assert result.category == Category.HIGH
    texts = [f.text.lower() for f in result.factors]
    assert "chuva forte prevista (30 mm em 1 h)" in texts
    assert "setor r3 vistoriado pela prefeitura" in texts


def test_ac062_r2_in_flood_extent_with_70mm_is_high() -> None:
    result = assess_sector(sector(grade=2, flood=True), rain(p1h=5.0, p24=70.0), "FRESH")
    assert result.susceptibility == 3
    assert result.category == Category.HIGH
    codes = [f.code for f in result.factors]
    assert "FLOOD_EXTENT" in codes and "RAIN_P24" in codes


@pytest.mark.parametrize("freshness", ["STALE", "UNAVAILABLE", "UNKNOWN"])
def test_ac063_stale_forecast_is_unknown_never_low(freshness: str) -> None:
    result = assess_sector(sector(), rain(p1h=0.0, p24=0.0), freshness)
    assert result.category == Category.UNKNOWN
    assert result.unknown_reason == f"FORECAST_{freshness}"
    assert result.rain_level is None


def test_delayed_forecast_still_counts() -> None:
    assert assess_sector(sector(), rain(p1h=30.0), "DELAYED").category == Category.HIGH


def test_missing_hours_beyond_tolerance_is_unknown() -> None:
    assert assess_sector(sector(), rain(hours=22), "FRESH").category == Category.LOW
    result = assess_sector(sector(), rain(hours=21), "FRESH")
    assert result.category == Category.UNKNOWN
    assert result.unknown_reason == "INCOMPLETE_WINDOW"


def test_sector_without_forecast_point_is_unknown() -> None:
    result = assess_sector(sector(key=None), None, "FRESH")
    assert result.category == Category.UNKNOWN
    assert result.unknown_reason == "NO_FORECAST_POINT"
    assert result.point_distance_km is None


def test_ac066_engine_is_deterministic_and_versioned() -> None:
    sectors = [
        SectorInput(
            i,
            grade=1 + i % 4,
            in_flood_extent=i % 3 == 0,
            nearby_occurrences=i % 5,
            point_key="p" if i % 7 else None,
            point_distance_km=2.0,
        )
        for i in range(40, 0, -1)
    ]
    rain_by_point = {"p": rain(p1h=27.0, p24=40.0, a72=55.0)}
    first = assess(sectors, rain_by_point, freshness="FRESH", now=NOW)
    second = assess(list(reversed(sectors)), rain_by_point, freshness="FRESH", now=NOW)
    assert first == second
    assert [a.sector_id for a in first.assessments] == list(range(1, 41))
    assert first.engine_version == ENGINE_VERSION
    assert first.valid_until == NOW + timedelta(hours=24)
    assert sum(first.counts.values()) == 40
    assert set(first.counts) == {c.value for c in Category}


def test_explanations_use_brazilian_number_format() -> None:
    assert format_mm(12.5) == "12,5"
    assert format_mm(30.0) == "30"
    assert format_mm(0.04) == "0"


def test_no_risk_label_uses_the_word_alerta() -> None:
    """BR-065/AC-067: o risco estimado nunca é chamado de alerta."""
    cases = [
        assess_sector(sector(grade=g, flood=True, nearby=3), rain(p1h=p, p24=p * 2, a72=a), f)
        for g in range(1, 5)
        for p in (0.0, 15.0, 30.0, 60.0)
        for a in (None, 10.0, 80.0)
        for f in ("FRESH", "STALE")
    ]
    for result in cases:
        for factor in result.factors:
            assert "alerta" not in factor.text.lower()

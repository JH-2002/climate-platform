"""T057 — montagem das entradas do motor: ponto mais próximo e chuva por ponto (FR-061)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.risk import ForecastPoint, haversine_km, nearest_point, rain_inputs

START = datetime(2026, 11, 19, 15, tzinfo=UTC)
ISSUED = datetime(2026, 11, 19, 15, 5, tzinfo=UTC)


def hours(offsets: range, value: float) -> dict[datetime, float]:
    return {START + timedelta(hours=h): value for h in offsets}


def test_haversine_known_distance() -> None:
    # Sé (centro) até o Mirante de Santana (A701): ~6,2 km
    assert haversine_km(-23.5505, -46.6333, -23.4963, -46.6201) == pytest.approx(6.17, abs=0.3)


def test_nearest_point_respects_max_distance() -> None:
    points = [
        ForecastPoint("a", -23.45, -46.62, ISSUED),
        ForecastPoint("b", -23.57, -46.62, ISSUED),
    ]
    key, dist = nearest_point(-23.55, -46.63, points, 25.0) or ("", 0.0)
    assert key == "b" and dist < 3
    # setor de Campo Limpo no recorte real: ~26 km do ponto do centro
    assert (
        nearest_point(-23.676, -46.7985, [ForecastPoint("c", -23.5149, -46.6105, ISSUED)], 25.0)
        is None
    )


def test_rain_window_and_antecedent() -> None:
    series = {**hours(range(-72, 0), 1.0), **hours(range(24), 0.5)}
    series[START + timedelta(hours=5)] = 31.0
    result = rain_inputs({"p": series}, START)["p"]
    assert result.p1h_max == 31.0
    assert result.p24 == pytest.approx(0.5 * 23 + 31.0)
    assert result.hours_available == 24
    assert result.a72 == pytest.approx(72.0)


def test_antecedent_is_missing_when_history_is_short() -> None:
    series = {**hours(range(-15, 0), 4.0), **hours(range(24), 0.0)}
    result = rain_inputs({"p": series}, START)["p"]
    assert result.a72 is None  # não inventa as horas que faltam
    assert result.p1h_max == 0.0


def test_window_counts_missing_hours() -> None:
    result = rain_inputs({"p": hours(range(20), 1.0)}, START)["p"]
    assert result.hours_available == 20
    assert result.p24 == 20.0


def test_point_with_no_window_values() -> None:
    result = rain_inputs({"p": hours(range(-5, 0), 1.0)}, START)["p"]
    assert result.p1h_max is None
    assert result.hours_available == 0

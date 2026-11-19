"""T013 — parser da previsão Open-Meteo com a resposta real gravada."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.integrations.open_meteo.forecast import build_params, parse_forecast, point_key
from app.tests.fixtures import OPEN_METEO_SP, load


def test_real_response_produces_all_points() -> None:
    result = parse_forecast(load(OPEN_METEO_SP))
    hourly = [p for p in result.points if p.resolution == "hourly"]
    daily = [p for p in result.points if p.resolution == "daily"]
    assert len(hourly) == 168 * 4
    assert len(daily) == 7 * 4
    assert result.missing_values == 0
    assert result.point_key == "-23.5149,-46.6105"


def test_wind_in_kmh_is_converted_to_ms() -> None:
    result = parse_forecast(load(OPEN_METEO_SP))
    first_wind = next(p for p in result.points if p.variable == "wind_speed")
    assert first_wind.unit == "m/s"
    assert first_wind.value == pytest.approx(4.0 / 3.6, abs=1e-3)


def test_times_are_utc_aware() -> None:
    result = parse_forecast(load(OPEN_METEO_SP))
    first = result.points[0]
    assert first.valid_at == datetime(2026, 11, 19, 0, 0, tzinfo=UTC)
    assert first.variable == "air_temperature"
    assert first.value == pytest.approx(21.7)


def test_local_times_are_converted_with_offset() -> None:
    payload = {
        "latitude": -23.5,
        "longitude": -46.6,
        "utc_offset_seconds": -10800,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {"time": ["2026-11-19T21:00"], "temperature_2m": [25.0]},
        "daily_units": {"time": "iso8601", "precipitation_sum": "mm"},
        "daily": {"time": ["2026-11-19"], "precipitation_sum": [None]},
    }
    result = parse_forecast(payload)
    assert result.points[0].valid_at == datetime(2026, 11, 20, 0, 0, tzinfo=UTC)
    assert result.missing_values == 1  # valor nulo não vira zero


def test_unexpected_unit_is_rejected() -> None:
    payload = load(OPEN_METEO_SP)
    payload["hourly_units"]["temperature_2m"] = "°F"
    with pytest.raises(ValueError, match="unidade"):
        parse_forecast(payload)


def test_length_mismatch_is_rejected() -> None:
    payload = load(OPEN_METEO_SP)
    payload["hourly"]["precipitation"] = payload["hourly"]["precipitation"][:10]
    with pytest.raises(ValueError, match="tamanho"):
        parse_forecast(payload)


def test_request_params_ask_for_ms_and_local_timezone() -> None:
    params = build_params(-23.55, -46.63)
    assert params["wind_speed_unit"] == "ms"
    assert params["timezone"] == "America/Sao_Paulo"
    assert params["forecast_days"] == "7"
    assert point_key(-23.514938, -46.610504) == "-23.5149,-46.6105"

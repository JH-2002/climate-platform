"""Previsão da Open-Meteo (`/v1/forecast`). Funções puras: montar parâmetros e interpretar.

Formato confirmado no smoke test de 2026-11-19. Todo dado daqui é `kind = FORECAST`
(Constituição §7): nunca é tratado como observação.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "America/Sao_Paulo"

# variável da fonte -> (variável canônica, unidade canônica)
HOURLY_VARIABLES: dict[str, tuple[str, str]] = {
    "temperature_2m": ("air_temperature", "°C"),
    "precipitation": ("precipitation", "mm"),
    "relative_humidity_2m": ("relative_humidity", "%"),
    "wind_speed_10m": ("wind_speed", "m/s"),
}
DAILY_VARIABLES: dict[str, tuple[str, str]] = {
    "temperature_2m_max": ("air_temperature_max", "°C"),
    "temperature_2m_min": ("air_temperature_min", "°C"),
    "precipitation_sum": ("precipitation_sum", "mm"),
    "precipitation_probability_max": ("precipitation_probability_max", "%"),
}

# unidade da fonte -> (unidade canônica, fator de conversão)
_UNIT_CONVERSIONS: dict[str, tuple[str, float]] = {
    "°C": ("°C", 1.0),
    "mm": ("mm", 1.0),
    "%": ("%", 1.0),
    "m/s": ("m/s", 1.0),
    "km/h": ("m/s", 1 / 3.6),
}


@dataclass(frozen=True)
class ForecastPoint:
    resolution: str  # "hourly" | "daily"
    valid_at: datetime  # UTC
    variable: str
    value: float
    unit: str


@dataclass(frozen=True)
class ForecastParseResult:
    latitude: float
    longitude: float
    point_key: str
    points: list[ForecastPoint]
    missing_values: int


# Horas anteriores à coleta (spec 005, FR-061): chuva estimada nas 72 h anteriores.
PAST_DAYS = 3


def build_params(
    lat: float, lon: float, days: int = 7, past_days: int = PAST_DAYS
) -> dict[str, str]:
    return {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "hourly": ",".join(HOURLY_VARIABLES),
        "daily": ",".join(DAILY_VARIABLES),
        "wind_speed_unit": "ms",
        "forecast_days": str(days),
        "past_days": str(past_days),
        "timezone": TIMEZONE,
    }


def point_key(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def _to_utc(local: str, offset_s: int) -> datetime:
    naive = datetime.fromisoformat(local)
    if naive.tzinfo is not None:
        return naive.astimezone(UTC)
    return (naive - timedelta(seconds=offset_s)).replace(tzinfo=UTC)


def _convert(value: Any, source_unit: str, expected_unit: str, field: str) -> float | None:
    if value is None:
        return None
    if source_unit not in _UNIT_CONVERSIONS:
        raise ValueError(f"unidade desconhecida para {field}: {source_unit!r}")
    canonical, factor = _UNIT_CONVERSIONS[source_unit]
    if canonical != expected_unit:
        raise ValueError(f"unidade incompatível para {field}: {source_unit!r}")
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number * factor, 3)


def _parse_block(
    payload: dict[str, Any],
    block: str,
    variables: dict[str, tuple[str, str]],
    offset_s: int,
) -> tuple[list[ForecastPoint], int]:
    data = payload.get(block)
    units = payload.get(f"{block}_units")
    if not isinstance(data, dict) or not isinstance(units, dict):
        return [], 0
    times = data.get("time")
    if not isinstance(times, list):
        raise ValueError(f"bloco {block} sem lista de horários")
    resolution = "hourly" if block == "hourly" else "daily"
    timestamps = [_to_utc(t, offset_s) for t in times]
    points: list[ForecastPoint] = []
    missing = 0
    for field, (variable, unit) in variables.items():
        values = data.get(field)
        if values is None:
            continue
        if len(values) != len(timestamps):
            raise ValueError(f"{block}.{field} com tamanho diferente da lista de horários")
        source_unit = str(units.get(field, ""))
        for valid_at, raw in zip(timestamps, values, strict=True):
            converted = _convert(raw, source_unit, unit, f"{block}.{field}")
            if converted is None:
                missing += 1
                continue
            points.append(ForecastPoint(resolution, valid_at, variable, converted, unit))
    return points, missing


def parse_forecast(payload: Any) -> ForecastParseResult:
    if not isinstance(payload, dict):
        raise ValueError("resposta inesperada: a previsão deve ser um objeto JSON")
    try:
        lat = float(payload["latitude"])
        lon = float(payload["longitude"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("previsão sem latitude/longitude") from None
    offset_s = int(payload.get("utc_offset_seconds") or 0)
    hourly, missing_h = _parse_block(payload, "hourly", HOURLY_VARIABLES, offset_s)
    daily, missing_d = _parse_block(payload, "daily", DAILY_VARIABLES, offset_s)
    return ForecastParseResult(
        latitude=lat,
        longitude=lon,
        point_key=point_key(lat, lon),
        points=hourly + daily,
        missing_values=missing_h + missing_d,
    )

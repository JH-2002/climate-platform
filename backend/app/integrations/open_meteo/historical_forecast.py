"""Open-Meteo Historical Forecast API — previsões arquivadas (spec 015, FR-210). Funções puras.

Série horária contínua montada com as primeiras horas de cada rodada do modelo ("best match").
É previsão de modelo (`kind = FORECAST`), não medição. Horários em UTC.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

HISTORICAL_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FIRST_DAY = date(2026, 1, 1)


@dataclass(frozen=True)
class HourlyRain:
    valid_at: datetime
    precipitation_mm: float


@dataclass(frozen=True)
class HistoricalForecastResult:
    values: list[HourlyRain]
    missing_values: int


def build_params(lat: float, lon: float, start: date, end: date) -> dict[str, str]:
    if end < start:
        raise ValueError("fim antes do início")
    return {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "precipitation",
        "timezone": "GMT",
    }


def parse_historical_forecast(payload: Any) -> HistoricalForecastResult:
    if not isinstance(payload, dict) or "hourly" not in payload:
        reason = payload.get("reason") if isinstance(payload, dict) else None
        raise ValueError(f"resposta sem bloco horário{f': {reason}' if reason else ''}")
    hourly = payload["hourly"]
    units = payload.get("hourly_units") or {}
    times = hourly.get("time")
    series = hourly.get("precipitation")
    if not isinstance(times, list) or not isinstance(series, list):
        raise ValueError("bloco horário sem horários ou sem precipitação")
    if len(times) != len(series):
        raise ValueError("tamanho diferente entre horários e precipitação")
    if units.get("precipitation") not in (None, "mm"):
        raise ValueError(f"unidade inesperada: {units.get('precipitation')!r}")
    values: list[HourlyRain] = []
    missing = 0
    for text, raw in zip(times, series, strict=True):
        if raw is None or not math.isfinite(float(raw)):
            missing += 1
            continue
        valid_at = datetime.fromisoformat(str(text)).replace(tzinfo=UTC)
        values.append(HourlyRain(valid_at, max(0.0, round(float(raw), 2))))
    return HistoricalForecastResult(values, missing)

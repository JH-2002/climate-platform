"""Open-Meteo Historical API — reanálise diária (spec 006, FR-081). Funções puras.

Formato confirmado em 2026-11-19 (SOURCES.md §12). Todo dado daqui é `kind = MODELED`.
A fonte devolve a coordenada da célula do modelo, que pode diferir do ponto pedido.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE = "America/Sao_Paulo"
FIRST_DAY = date(1991, 1, 1)

# variável da fonte -> (variável canônica, unidade)
DAILY_VARIABLES: dict[str, tuple[str, str]] = {
    "precipitation_sum": ("precipitation_sum", "mm"),
    "temperature_2m_max": ("air_temperature_max", "°C"),
    "temperature_2m_min": ("air_temperature_min", "°C"),
    "temperature_2m_mean": ("air_temperature_mean", "°C"),
}


@dataclass(frozen=True)
class DailyValue:
    day: date
    variable: str
    value: float
    unit: str


@dataclass(frozen=True)
class ArchiveParseResult:
    cell_latitude: float
    cell_longitude: float
    values: list[DailyValue]
    missing_values: int

    @property
    def cell_key(self) -> str:
        return f"{self.cell_latitude:.4f},{self.cell_longitude:.4f}"


def build_params(lat: float, lon: float, start: date, end: date) -> dict[str, str]:
    if end < start:
        raise ValueError("fim antes do início")
    return {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
    }


def parse_archive(payload: Any) -> ArchiveParseResult:
    if not isinstance(payload, dict) or "daily" not in payload:
        reason = payload.get("reason") if isinstance(payload, dict) else None
        raise ValueError(f"resposta sem bloco diário{f': {reason}' if reason else ''}")
    daily = payload["daily"]
    units = payload.get("daily_units") or {}
    times = daily.get("time")
    if not isinstance(times, list):
        raise ValueError("bloco diário sem datas")
    values: list[DailyValue] = []
    missing = 0
    for source_var, (variable, unit) in DAILY_VARIABLES.items():
        series = daily.get(source_var)
        if series is None:
            raise ValueError(f"variável ausente: {source_var}")
        if len(series) != len(times):
            raise ValueError(f"tamanho diferente entre datas e {source_var}")
        if units.get(source_var) not in (None, unit):
            raise ValueError(f"unidade inesperada para {source_var}: {units.get(source_var)!r}")
        for day_text, raw in zip(times, series, strict=True):
            if raw is None or not math.isfinite(float(raw)):
                missing += 1
                continue
            values.append(DailyValue(date.fromisoformat(day_text), variable, float(raw), unit))
    return ArchiveParseResult(
        cell_latitude=float(payload["latitude"]),
        cell_longitude=float(payload["longitude"]),
        values=values,
        missing_values=missing,
    )

"""Previsão por coordenada para o painel do clima (spec 003).

As funções puras (hora corrente, pivot, acumulados) ficam separadas das consultas ao banco.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from geoalchemy2 import Geography
from pydantic import BaseModel
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import data_sources, weather_forecasts

FORECAST_SOURCE = "open-meteo-forecast"
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
MAX_POINT_DISTANCE_KM = 25.0
HOURLY_WINDOW_H = 48
DAILY_DAYS = 7
OUTLOOK_HOURS = (1, 3, 24, 72)

HOURLY_FIELDS = ("air_temperature", "precipitation", "relative_humidity", "wind_speed")
DAILY_FIELDS = (
    "air_temperature_max",
    "air_temperature_min",
    "precipitation_sum",
    "precipitation_probability_max",
)
UNITS = {
    "air_temperature": "°C",
    "precipitation": "mm",
    "relative_humidity": "%",
    "wind_speed": "m/s",
    "air_temperature_max": "°C",
    "air_temperature_min": "°C",
    "precipitation_sum": "mm",
    "precipitation_probability_max": "%",
}


class HourlyValues(BaseModel):
    valid_at: datetime
    air_temperature: float | None = None
    precipitation: float | None = None
    relative_humidity: float | None = None
    wind_speed: float | None = None


class DailyValues(BaseModel):
    date: date
    air_temperature_max: float | None = None
    air_temperature_min: float | None = None
    precipitation_sum: float | None = None
    precipitation_probability_max: float | None = None


class PrecipitationOutlook(BaseModel):
    hours: int
    total_mm: float
    complete: bool
    hours_available: int


@dataclass(frozen=True)
class ForecastPointInfo:
    point_key: str
    latitude: float
    longitude: float
    distance_km: float
    issued_at: datetime


# --- funções puras -------------------------------------------------------------------------


def current_hour(now: datetime) -> datetime:
    """Hora cheia corrente em UTC (BR-040)."""
    return now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def local_midnight_utc(now: datetime) -> datetime:
    """Meia-noite de hoje no horário de Brasília, expressa em UTC (BR-042)."""
    local = now.astimezone(LOCAL_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def pivot_hourly(rows: Iterable[tuple[datetime, str, float]]) -> list[HourlyValues]:
    by_time: dict[datetime, dict[str, float]] = defaultdict(dict)
    for valid_at, variable, value in rows:
        if variable in HOURLY_FIELDS:
            by_time[valid_at.astimezone(UTC)][variable] = value
    return [HourlyValues.model_validate({"valid_at": t, **v}) for t, v in sorted(by_time.items())]


def pivot_daily(rows: Iterable[tuple[datetime, str, float]]) -> list[DailyValues]:
    by_day: dict[date, dict[str, float]] = defaultdict(dict)
    for valid_at, variable, value in rows:
        if variable in DAILY_FIELDS:
            by_day[valid_at.astimezone(LOCAL_TZ).date()][variable] = value
    return [DailyValues.model_validate({"date": d, **v}) for d, v in sorted(by_day.items())]


def precipitation_outlook(
    hourly_precipitation: Mapping[datetime, float], start: datetime, hours: int
) -> PrecipitationOutlook:
    """Soma N horas a partir de `start`; incompleto se faltar alguma hora (BR-041)."""
    values = [hourly_precipitation.get(start + timedelta(hours=h)) for h in range(hours)]
    present = [v for v in values if v is not None]
    return PrecipitationOutlook(
        hours=hours,
        total_mm=round(sum(present), 2),
        complete=len(present) == hours,
        hours_available=len(present),
    )


# --- consultas -------------------------------------------------------------------------------


def _origin(lat: float, lon: float) -> Any:
    return cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)


async def nearest_point(
    session: AsyncSession, *, lat: float, lon: float, max_km: float = MAX_POINT_DISTANCE_KM
) -> ForecastPointInfo | None:
    t = weather_forecasts
    origin = _origin(lat, lon)
    distance = func.ST_Distance(t.c.point, origin)
    row = (
        await session.execute(
            select(
                t.c.point_key,
                func.ST_Y(func.geometry(t.c.point)).label("latitude"),
                func.ST_X(func.geometry(t.c.point)).label("longitude"),
                (distance / 1000.0).label("distance_km"),
            )
            .join(data_sources, data_sources.c.id == t.c.source_id)
            .where(data_sources.c.code == FORECAST_SOURCE)
            .where(func.ST_DWithin(t.c.point, origin, max_km * 1000.0))
            .order_by(distance)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    issued_at = (
        await session.execute(select(func.max(t.c.issued_at)).where(t.c.point_key == row.point_key))
    ).scalar_one()
    return ForecastPointInfo(
        point_key=row.point_key,
        latitude=float(row.latitude),
        longitude=float(row.longitude),
        distance_km=float(row.distance_km),
        issued_at=issued_at,
    )


async def _rows(
    session: AsyncSession, point_key: str, resolution: str, start: datetime, end: datetime
) -> list[tuple[datetime, str, float]]:
    t = weather_forecasts
    result = await session.execute(
        select(t.c.valid_at, t.c.variable, t.c.value)
        .where(
            t.c.point_key == point_key,
            t.c.resolution == resolution,
            t.c.valid_at >= start,
            t.c.valid_at < end,
        )
        .order_by(t.c.valid_at)
    )
    return [(r.valid_at, r.variable, float(r.value)) for r in result]


async def hourly_series(
    session: AsyncSession, point_key: str, start: datetime, hours: int
) -> list[HourlyValues]:
    rows = await _rows(session, point_key, "hourly", start, start + timedelta(hours=hours))
    return pivot_hourly(rows)


async def hourly_precipitation(
    session: AsyncSession, point_key: str, start: datetime, hours: int
) -> dict[datetime, float]:
    rows = await _rows(session, point_key, "hourly", start, start + timedelta(hours=hours))
    return {v.astimezone(UTC): value for v, var, value in rows if var == "precipitation"}


async def daily_series(
    session: AsyncSession, point_key: str, start: datetime, days: int
) -> list[DailyValues]:
    rows = await _rows(session, point_key, "daily", start, start + timedelta(days=days))
    return pivot_daily(rows)

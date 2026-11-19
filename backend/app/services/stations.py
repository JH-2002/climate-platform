"""Consultas de estações (FR-031) e de observações."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from pydantic import BaseModel
from sqlalchemy import Select, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import BoundingBox
from app.models.tables import data_sources, weather_observations, weather_stations


class Station(BaseModel):
    id: int
    code: str
    name: str
    source: str
    state: str | None
    latitude: float
    longitude: float
    altitude_m: float | None
    status: str
    last_seen_at: datetime


class StationWithDistance(Station):
    distance_km: float


class Observation(BaseModel):
    observed_at: datetime
    variable: str
    value: float | None
    unit: str
    kind: str
    mode: str
    quality_flag: str


def _station_columns() -> list[Any]:
    return [
        weather_stations.c.id,
        weather_stations.c.external_code.label("code"),
        weather_stations.c.name,
        data_sources.c.code.label("source"),
        weather_stations.c.state,
        func.ST_Y(func.geometry(weather_stations.c.location)).label("latitude"),
        func.ST_X(func.geometry(weather_stations.c.location)).label("longitude"),
        weather_stations.c.altitude_m,
        weather_stations.c.status,
        weather_stations.c.last_seen_at,
    ]


def _base_query(*extra: Any) -> Select[Any]:
    return select(*_station_columns(), *extra).join(
        data_sources, data_sources.c.id == weather_stations.c.source_id
    )


def _envelope(bbox: BoundingBox) -> Any:
    return func.ST_MakeEnvelope(bbox.lon_min, bbox.lat_min, bbox.lon_max, bbox.lat_max, 4326)


async def list_stations(
    session: AsyncSession,
    *,
    bbox: BoundingBox | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Station], int]:
    conditions: list[Any] = []
    if bbox is not None:
        conditions.append(
            func.ST_Intersects(func.geometry(weather_stations.c.location), _envelope(bbox))
        )
    if status is not None:
        conditions.append(weather_stations.c.status == status)
    where = and_(*conditions) if conditions else None

    query = _base_query().order_by(weather_stations.c.name).limit(limit).offset(offset)
    count = select(func.count()).select_from(weather_stations)
    if where is not None:
        query = query.where(where)
        count = count.where(where)
    rows = (await session.execute(query)).mappings().all()
    total = int((await session.execute(count)).scalar_one())
    return [Station.model_validate(dict(r)) for r in rows], total


async def nearby_stations(
    session: AsyncSession, *, lat: float, lon: float, radius_km: float, limit: int
) -> list[StationWithDistance]:
    origin = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    distance = func.ST_Distance(weather_stations.c.location, origin)
    query = (
        _base_query((distance / 1000.0).label("distance_km"))
        .where(func.ST_DWithin(weather_stations.c.location, origin, radius_km * 1000.0))
        .order_by(distance)
        .limit(limit)
    )
    rows = (await session.execute(query)).mappings().all()
    return [StationWithDistance.model_validate(dict(r)) for r in rows]


async def get_station(session: AsyncSession, station_id: int) -> Station | None:
    row = (
        (await session.execute(_base_query().where(weather_stations.c.id == station_id)))
        .mappings()
        .one_or_none()
    )
    return Station.model_validate(dict(row)) if row else None


async def list_observations(
    session: AsyncSession,
    *,
    station_id: int,
    start: datetime,
    end: datetime,
    variables: list[str] | None,
    include_flagged: bool,
) -> list[Observation]:
    t = weather_observations
    query = (
        select(
            t.c.observed_at, t.c.variable, t.c.value, t.c.unit, t.c.kind, t.c.mode, t.c.quality_flag
        )
        .where(t.c.station_id == station_id, t.c.observed_at >= start, t.c.observed_at <= end)
        .order_by(t.c.observed_at, t.c.variable)
    )
    if variables:
        query = query.where(t.c.variable.in_(variables))
    if not include_flagged:
        query = query.where(t.c.quality_flag != "FAILED")
    rows = (await session.execute(query)).mappings().all()
    return [Observation.model_validate(dict(r)) for r in rows]

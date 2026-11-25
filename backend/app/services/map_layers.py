"""Camadas do mapa (spec 004): estações e pontos de previsão com chuva prevista em 24 h."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import BoundingBox
from app.models.tables import data_sources, weather_forecasts
from app.services import forecast as fc
from app.services.geojson import Feature, point_feature
from app.services.stations import list_stations

MAX_STATIONS = 500


async def station_features(session: AsyncSession, bbox: BoundingBox | None) -> list[Feature]:
    stations, _ = await list_stations(session, bbox=bbox, status=None, limit=MAX_STATIONS, offset=0)
    return [
        point_feature(
            s.longitude,
            s.latitude,
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "status": s.status,
                "source": s.source,
                "altitude_m": s.altitude_m,
            },
            fid=s.id,
        )
        for s in stations
    ]


async def forecast_point_features(session: AsyncSession, now: datetime) -> list[Feature]:
    t = weather_forecasts
    points = (
        await session.execute(
            select(
                t.c.point_key,
                func.ST_Y(func.geometry(t.c.point)).label("latitude"),
                func.ST_X(func.geometry(t.c.point)).label("longitude"),
                func.max(t.c.issued_at).label("issued_at"),
            )
            .join(data_sources, data_sources.c.id == t.c.source_id)
            .where(data_sources.c.code == fc.FORECAST_SOURCE)
            .where(t.c.point_key.in_(fc.active_point_keys()))
            .group_by(t.c.point_key, t.c.point)
            .order_by(t.c.point_key)
        )
    ).all()

    start = fc.current_hour(now)
    features: list[Feature] = []
    for index, p in enumerate(points):
        hourly = await fc.hourly_series(session, p.point_key, start, 1)
        precipitation = await fc.hourly_precipitation(session, p.point_key, start, 24)
        outlook = fc.precipitation_outlook(precipitation, start, 24)
        properties: dict[str, Any] = {
            "point_key": p.point_key,
            "kind": "FORECAST",
            "issued_at": p.issued_at.isoformat(),
            "valid_from": start.isoformat(),
            "air_temperature_now": hourly[0].air_temperature if hourly else None,
            "precipitation_24h": outlook.total_mm,
            "precipitation_24h_complete": outlook.complete,
            "precipitation_24h_hours": outlook.hours_available,
        }
        features.append(
            point_feature(float(p.longitude), float(p.latitude), properties, fid=index + 1)
        )
    return features

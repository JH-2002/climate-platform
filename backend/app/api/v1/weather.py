"""Painel do clima: previsão por coordenada (spec 003)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.deps import ClockDep, SessionDep, SettingsDep, get_clock
from app.services import forecast as fc
from app.services.freshness import Freshness, Reason
from app.services.sources import list_source_status

__all__ = ["get_clock", "router"]

router = APIRouter(prefix="/weather", tags=["clima"])


class PointOut(BaseModel):
    latitude: float
    longitude: float
    distance_km: float


class SourceOut(BaseModel):
    code: str
    name: str
    attribution: str
    freshness: Freshness
    reason: Reason
    last_success_at: datetime | None


class ForecastResponse(BaseModel):
    kind: Literal["FORECAST"] = "FORECAST"
    point: PointOut
    source: SourceOut
    issued_at: datetime
    now: fc.HourlyValues | None
    hourly: list[fc.HourlyValues]
    daily: list[fc.DailyValues]
    precipitation_outlook: list[fc.PrecipitationOutlook]
    units: dict[str, str]


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Previsão do ponto coletado mais próximo",
    responses={404: {"description": "Sem previsão coletada até 25 km do local"}},
)
async def forecast(
    session: SessionDep,
    settings: SettingsDep,
    clock: ClockDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> ForecastResponse:
    """Previsão de modelo (`kind = FORECAST`): nunca é medição (Constituição §7, ADR-007)."""
    now = clock()
    point = await fc.nearest_point(session, lat=lat, lon=lon)
    if point is None:
        raise HTTPException(
            status_code=404,
            detail="Não há previsão coletada até 25 km deste local. "
            "Adicione o ponto em FORECAST_POINTS para passar a coletá-lo.",
        )

    credentials = {"inmet-observations": settings.inmet_token_value is not None}
    sources = await list_source_status(session, now=now, credentials=credentials)
    source = next(s for s in sources if s.code == fc.FORECAST_SOURCE)

    start = fc.current_hour(now)
    hourly = await fc.hourly_series(session, point.point_key, start, fc.HOURLY_WINDOW_H)
    precipitation = await fc.hourly_precipitation(
        session, point.point_key, start, max(fc.OUTLOOK_HOURS)
    )
    daily = await fc.daily_series(
        session, point.point_key, fc.local_midnight_utc(now), fc.DAILY_DAYS
    )
    current = next((h for h in hourly if h.valid_at == start), None)

    return ForecastResponse(
        point=PointOut(
            latitude=point.latitude, longitude=point.longitude, distance_km=point.distance_km
        ),
        source=SourceOut(
            code=source.code,
            name=source.name,
            attribution=source.attribution,
            freshness=source.freshness,
            reason=source.reason,
            last_success_at=source.last_success_at,
        ),
        issued_at=point.issued_at,
        now=current,
        hourly=hourly,
        daily=daily,
        precipitation_outlook=[
            fc.precipitation_outlook(precipitation, start, h) for h in fc.OUTLOOK_HOURS
        ],
        units=fc.UNITS,
    )

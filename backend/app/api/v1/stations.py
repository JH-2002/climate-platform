"""Estações meteorológicas (FR-031) e suas observações."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.deps import SessionDep, SettingsDep
from app.core.geo import BoundingBox
from app.services.freshness import Freshness, Reason
from app.services.sources import list_source_status
from app.services.stations import (
    Observation,
    Station,
    StationWithDistance,
    get_station,
    list_observations,
    list_stations,
    nearby_stations,
)

router = APIRouter(prefix="/stations", tags=["estações"])

MAX_OBSERVATION_RANGE = timedelta(days=31)
BBOX_HELP = "lon_min,lat_min,lon_max,lat_max (WGS84). Ex.: -46.83,-24.01,-46.36,-23.35"
StationStatus = Literal["OPERATIONAL", "FAULT", "INACTIVE", "UNKNOWN"]


class StationPage(BaseModel):
    items: list[Station]
    total: int
    limit: int
    offset: int


class NearbyStations(BaseModel):
    items: list[StationWithDistance]


class Availability(BaseModel):
    source: str
    freshness: Freshness
    reason: Reason


class StationObservations(BaseModel):
    station: Station
    start: datetime
    end: datetime
    availability: Availability
    items: list[Observation]


@router.get("", response_model=StationPage, summary="Lista paginada de estações")
async def stations(
    session: SessionDep,
    bbox: Annotated[str | None, Query(description=BBOX_HELP)] = None,
    status: StationStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StationPage:
    box = None
    if bbox is not None:
        try:
            box = BoundingBox.parse(bbox)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"bbox inválido: {exc}") from None
    items, total = await list_stations(session, bbox=box, status=status, limit=limit, offset=offset)
    return StationPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/nearby", response_model=NearbyStations, summary="Estações próximas de um ponto")
async def nearby(
    session: SessionDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=200)] = 30,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> NearbyStations:
    items = await nearby_stations(session, lat=lat, lon=lon, radius_km=radius_km, limit=limit)
    return NearbyStations(items=items)


@router.get(
    "/{station_id}/observations",
    response_model=StationObservations,
    summary="Observações de uma estação num período",
)
async def observations(
    session: SessionDep,
    settings: SettingsDep,
    station_id: int,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    variables: Annotated[str | None, Query(description="Lista separada por vírgula")] = None,
    include_flagged: bool = False,
) -> StationObservations:
    station = await get_station(session, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Estação não encontrada.")
    end_at = (end or datetime.now(UTC)).astimezone(UTC)
    start_at = (start or end_at - timedelta(days=1)).astimezone(UTC)
    if start_at > end_at:
        raise HTTPException(status_code=422, detail="O início do período é posterior ao fim.")
    if end_at - start_at > MAX_OBSERVATION_RANGE:
        raise HTTPException(status_code=422, detail="O período máximo é de 31 dias.")

    credentials = {"inmet-observations": settings.inmet_token_value is not None}
    sources = await list_source_status(session, now=datetime.now(UTC), credentials=credentials)
    obs_source = next(s for s in sources if s.code == "inmet-observations")

    items = await list_observations(
        session,
        station_id=station_id,
        start=start_at,
        end=end_at,
        variables=[v.strip() for v in variables.split(",") if v.strip()] if variables else None,
        include_flagged=include_flagged,
    )
    return StationObservations(
        station=station,
        start=start_at,
        end=end_at,
        availability=Availability(
            source=obs_source.code, freshness=obs_source.freshness, reason=obs_source.reason
        ),
        items=items,
    )

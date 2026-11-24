"""Geointeligência (spec 008): bacias, terreno de setor e de ponto, perfil e estado do DEM."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.deps import ClockDep, SessionDep, SettingsDep
from app.services.geo import (
    BasinDetail,
    BasinList,
    BasinSort,
    DemStatus,
    PointTerrain,
    Profile,
    ProfileError,
    SectorTerrain,
    TerrainUnavailableError,
    basin_detail,
    dem_status,
    list_basins,
    parse_profile_points,
    point_terrain,
    profile,
    require_terrain,
    sector_terrain_detail,
)

router = APIRouter(prefix="/geo", tags=["geointeligência"])


def _unavailable(exc: TerrainUnavailableError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/dem", response_model=DemStatus, summary="Estado do relevo (Copernicus DEM)")
async def read_dem(session: SessionDep, settings: SettingsDep) -> DemStatus:
    return await dem_status(session, settings)


@router.get("/basins", response_model=BasinList, summary="Bacias com setores, risco e piscinões")
async def read_basins(session: SessionDep, clock: ClockDep, ordem: BasinSort = "alto") -> BasinList:
    return await list_basins(session, clock(), ordem)


@router.get("/basins/{basin_id}", response_model=BasinDetail, summary="Ficha de uma bacia")
async def read_basin(basin_id: int, session: SessionDep, clock: ClockDep) -> BasinDetail:
    detail = await basin_detail(session, basin_id, clock())
    if detail is None:
        raise HTTPException(status_code=404, detail="Bacia não encontrada.")
    return detail


@router.get(
    "/sectors/{sector_id}/terrain",
    response_model=SectorTerrain,
    summary="Terreno de um setor de risco",
)
async def read_sector_terrain(sector_id: int, session: SessionDep) -> SectorTerrain:
    terrain = await sector_terrain_detail(session, sector_id)
    if terrain is None:
        raise HTTPException(
            status_code=404,
            detail="Terreno deste setor ainda não calculado (aguarda a hidrografia e o relevo).",
        )
    return terrain


@router.get("/elevation", response_model=PointTerrain, summary="Terreno num ponto")
async def read_elevation(
    session: SessionDep,
    settings: SettingsDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> PointTerrain:
    try:
        dem = await require_terrain(session, settings)
    except TerrainUnavailableError as exc:
        raise _unavailable(exc) from None
    if not dem.spec.contains(lon, lat):
        raise HTTPException(status_code=422, detail="Ponto fora da área do relevo.")
    return await point_terrain(session, dem, lat, lon)


@router.get("/profile", response_model=Profile, summary="Perfil de elevação entre pontos")
async def read_profile(
    session: SessionDep,
    settings: SettingsDep,
    pontos: Annotated[str, Query(max_length=400, description="lon,lat;lon,lat;…")],
) -> Profile:
    try:
        points = parse_profile_points(pontos)
        dem = await require_terrain(session, settings)
        return await profile(session, dem, points)
    except ProfileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except TerrainUnavailableError as exc:
        raise _unavailable(exc) from None

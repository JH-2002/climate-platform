"""Risco de alagamento estimado pelo sistema (spec 005). Estimativa experimental, não alerta."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.deps import ClockDep, SessionDep
from app.services.risk import (
    DISCLAIMER,
    RiskArea,
    RiskAreaDetail,
    RiskSummary,
    list_risk_areas,
    list_subprefectures,
    nearest_risk_area,
    risk_area_detail,
    risk_summary,
)

router = APIRouter(prefix="/risk", tags=["risco estimado"])

CategoryFilter = Literal["LOW", "MODERATE", "HIGH", "CRITICAL", "UNKNOWN"]
NEAREST_MAX_KM = 2.0


class RiskAreaPage(BaseModel):
    items: list[RiskArea]
    total: int
    limit: int
    offset: int
    subprefectures: list[str]
    disclaimer: str = DISCLAIMER


class NearestRiskArea(BaseModel):
    area: RiskArea | None
    distance_m: float | None
    max_distance_km: float = NEAREST_MAX_KM
    disclaimer: str = DISCLAIMER


@router.get("/summary", response_model=RiskSummary, summary="Resumo da última estimativa")
async def summary(session: SessionDep, clock: ClockDep) -> RiskSummary:
    return await risk_summary(session, clock())


@router.get("/areas", response_model=RiskAreaPage, summary="Setores com risco estimado")
async def areas(
    session: SessionDep,
    category: CategoryFilter | None = None,
    subprefecture: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RiskAreaPage:
    items, total = await list_risk_areas(
        session, category=category, subprefecture=subprefecture, limit=limit, offset=offset
    )
    return RiskAreaPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        subprefectures=await list_subprefectures(session),
    )


@router.get("/nearest", response_model=NearestRiskArea, summary="Setor mais próximo (até 2 km)")
async def nearest(
    session: SessionDep,
    clock: ClockDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> NearestRiskArea:
    found = await nearest_risk_area(session, lat, lon, NEAREST_MAX_KM, clock())
    if found is None:
        return NearestRiskArea(area=None, distance_m=None)
    area, distance = found
    return NearestRiskArea(area=area, distance_m=round(distance, 1))


@router.get("/areas/{sector_id}", response_model=RiskAreaDetail, summary="Detalhe de um setor")
async def area_detail(sector_id: int, session: SessionDep, clock: ClockDep) -> RiskAreaDetail:
    detail = await risk_area_detail(session, sector_id, clock())
    if detail is None:
        raise HTTPException(status_code=404, detail="setor não encontrado ou sem estimativa")
    return detail

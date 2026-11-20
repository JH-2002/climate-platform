"""Análises (spec 006): catálogo, estatísticas descritivas, KPIs e insights por regra."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.v1.deps import ClockDep, SessionDep, SettingsDep
from app.core.config import Settings
from app.services.analytics import (
    DatasetInfo,
    DescribeError,
    DescribeResult,
    InsightsResponse,
    KpisResponse,
    compute_insights,
    compute_kpis,
    describe_dataset,
    list_datasets,
)

router = APIRouter(prefix="/analytics", tags=["análises"])

CACHE_SHORT = "public, max-age=60"
CACHE_LONG = "public, max-age=600"


def _credentials(settings: Settings) -> dict[str, bool]:
    return {"inmet-observations": settings.inmet_token_value is not None}


@router.get("/datasets", response_model=list[DatasetInfo], summary="Catálogo de dados")
async def datasets(
    session: SessionDep, settings: SettingsDep, clock: ClockDep, response: Response
) -> list[DatasetInfo]:
    response.headers["Cache-Control"] = CACHE_SHORT
    return await list_datasets(session, clock(), _credentials(settings))


@router.get(
    "/datasets/{dataset_id}/describe",
    response_model=DescribeResult,
    summary="Estatísticas descritivas de uma variável",
)
async def describe(
    dataset_id: str,
    session: SessionDep,
    response: Response,
    variable: Annotated[str, Query(max_length=60)],
    start: date,
    end: date,
    location: Annotated[str | None, Query(max_length=60)] = None,
) -> DescribeResult:
    if (end - start).days > 366 * 100:
        raise HTTPException(status_code=422, detail="intervalo máximo: 100 anos")
    try:
        result = await describe_dataset(session, dataset_id, variable, location, start, end)
    except DescribeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    response.headers["Cache-Control"] = CACHE_LONG
    return result


@router.get("/kpis", response_model=KpisResponse, summary="Indicadores do painel executivo")
async def kpis(
    session: SessionDep, settings: SettingsDep, clock: ClockDep, response: Response
) -> KpisResponse:
    response.headers["Cache-Control"] = CACHE_SHORT
    return await compute_kpis(session, clock(), _credentials(settings))


@router.get(
    "/insights", response_model=InsightsResponse, summary="Insights por regras documentadas"
)
async def insights(
    session: SessionDep, settings: SettingsDep, clock: ClockDep, response: Response
) -> InsightsResponse:
    response.headers["Cache-Control"] = CACHE_SHORT
    return await compute_insights(session, clock(), _credentials(settings))

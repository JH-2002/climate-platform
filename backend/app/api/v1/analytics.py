"""Análises (spec 006): catálogo, estatísticas descritivas, KPIs e insights por regra."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

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
from app.services.analytics_series import (
    ClimatologyResponse,
    DistributionResponse,
    RankingResponse,
    RiskHistoryResponse,
    SeriesError,
    SeriesResponse,
    SourceHealth,
    TrendsResponse,
    get_climatology,
    get_distribution,
    get_ranking,
    get_risk_history,
    get_series,
    get_sources_health,
    get_trends,
    series_csv,
)
from app.services.risk_evaluation import RiskEvaluation, latest_evaluation

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


Grain = Literal["day", "week", "month", "year"]
Agg = Literal["sum", "mean", "min", "max", "count"]
Compare = Literal["normal", "previous_period", "same_period_last_year"]
Location = Annotated[str | None, Query(max_length=80)]


async def _series(
    session: SessionDep,
    clock: ClockDep,
    dataset: str,
    variable: str,
    start: date,
    end: date,
    grain: Grain,
    agg: Agg,
    location: str | None,
    compare: Compare | None,
) -> SeriesResponse:
    try:
        return await get_series(
            session,
            dataset=dataset,
            variable=variable,
            location=location,
            start=start,
            end=end,
            grain=grain,
            agg=agg,
            compare=compare,
            now=clock(),
        )
    except SeriesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/series", response_model=SeriesResponse, summary="Série agregada (Studio)")
async def series(
    session: SessionDep,
    clock: ClockDep,
    response: Response,
    dataset: Annotated[str, Query(max_length=60)],
    variable: Annotated[str, Query(max_length=60)],
    start: date,
    end: date,
    grain: Grain = "month",
    agg: Agg = "sum",
    location: Location = None,
    compare: Compare | None = None,
) -> SeriesResponse:
    result = await _series(
        session, clock, dataset, variable, start, end, grain, agg, location, compare
    )
    response.headers["Cache-Control"] = CACHE_LONG
    return result


@router.get("/series.csv", response_class=PlainTextResponse, summary="Série agregada em CSV")
async def series_export(
    session: SessionDep,
    clock: ClockDep,
    dataset: Annotated[str, Query(max_length=60)],
    variable: Annotated[str, Query(max_length=60)],
    start: date,
    end: date,
    grain: Grain = "month",
    agg: Agg = "sum",
    location: Location = None,
    compare: Compare | None = None,
) -> PlainTextResponse:
    result = await _series(
        session, clock, dataset, variable, start, end, grain, agg, location, compare
    )
    filename = f"{dataset}_{variable}_{start}_{end}_{grain}.csv"
    return PlainTextResponse(
        series_csv(result, clock()),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/climatology", response_model=ClimatologyResponse, summary="Climatologia mensal")
async def climatology(
    session: SessionDep,
    response: Response,
    dataset: Annotated[str, Query(max_length=60)],
    variable: Annotated[str, Query(max_length=60)],
    location: Location = None,
    start_year: Annotated[int, Query(ge=1900, le=2100)] = 1991,
    end_year: Annotated[int, Query(ge=1900, le=2100)] = 2020,
) -> ClimatologyResponse:
    try:
        result = await get_climatology(
            session,
            dataset=dataset,
            variable=variable,
            location=location,
            start_year=start_year,
            end_year=end_year,
        )
    except SeriesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    response.headers["Cache-Control"] = CACHE_LONG
    return result


@router.get(
    "/distribution", response_model=DistributionResponse, summary="Distribuição dos dias de chuva"
)
async def distribution(
    session: SessionDep,
    response: Response,
    location: Annotated[str, Query(max_length=80)],
    start: date,
    end: date,
) -> DistributionResponse:
    response.headers["Cache-Control"] = CACHE_LONG
    return await get_distribution(session, location=location, start=start, end=end)


@router.get("/ranking", response_model=RankingResponse, summary="Ranking por local")
async def ranking(
    session: SessionDep,
    response: Response,
    dataset: Annotated[str, Query(max_length=60)],
    variable: Annotated[str, Query(max_length=60)],
    start: date,
    end: date,
    agg: Agg = "sum",
) -> RankingResponse:
    try:
        result = await get_ranking(
            session, dataset=dataset, variable=variable, agg=agg, start=start, end=end
        )
    except SeriesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    response.headers["Cache-Control"] = CACHE_LONG
    return result


@router.get("/trends", response_model=TrendsResponse, summary="Tendências históricas (IAG/USP)")
async def trends(session: SessionDep, clock: ClockDep, response: Response) -> TrendsResponse:
    response.headers["Cache-Control"] = CACHE_LONG
    return await get_trends(session, clock())


@router.get("/risk-history", response_model=RiskHistoryResponse, summary="Histórico do risco")
async def risk_history(
    session: SessionDep,
    clock: ClockDep,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> RiskHistoryResponse:
    return await get_risk_history(session, clock(), days)


@router.get(
    "/sources-health", response_model=list[SourceHealth], summary="Disponibilidade das fontes"
)
async def sources_health(
    session: SessionDep, settings: SettingsDep, clock: ClockDep
) -> list[SourceHealth]:
    return await get_sources_health(session, clock(), _credentials(settings))


@router.get(
    "/risk-evaluation",
    response_model=RiskEvaluation,
    summary="Avaliação retrospectiva do motor de risco (spec 015)",
    responses={404: {"description": "Avaliação ainda não calculada"}},
)
async def risk_evaluation(session: SessionDep, response: Response) -> RiskEvaluation:
    """Retroteste do motor com previsão arquivada × ocorrências do GeoSampa (ADR-018)."""
    result = await latest_evaluation(session)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="A avaliação do motor ainda não foi calculada (roda uma vez por dia).",
        )
    response.headers["Cache-Control"] = CACHE_LONG
    return result

"""Análises (spec 006, Parte B): séries, climatologia, distribuição, ranking, tendências,
histórico do risco, saúde das fontes e exportação CSV.

Agrega no PostgreSQL (`date_trunc`) e aplica no Python só regras puras de `app.analytics`.
"""

from __future__ import annotations

import calendar
import csv
import io
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Date, Integer, case, cast, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.catalog import DATASETS, Dataset, Variable, aggregation_error, grain_error
from app.analytics.climatology import (
    NORMAL_END,
    NORMAL_START,
    annual_totals,
    monthly_normals,
    moving_average,
)
from app.analytics.series import (
    CompareMode,
    Grain,
    Resolution,
    bucket_start,
    buckets,
    expected_count,
    finalize,
    histogram,
    shifted_window,
)
from app.analytics.stats import percentile
from app.models.tables import (
    climate_daily,
    data_sources,
    flood_occurrences,
    hydro_risk_sectors,
    ingestion_runs,
    published_normals,
    rain_monthly_observed,
    risk_assessments,
    risk_runs,
    weather_forecasts,
)
from app.services.analytics import LOCAL_TZ
from app.services.sources import list_source_status

MAX_POINTS = 5000
CATEGORIES = ("CRITICAL", "HIGH", "MODERATE", "LOW", "UNKNOWN")
DAILY_ONLY = frozenset({"forecast-hourly", "risk-assessments", "ingestion-runs"})


class SeriesError(ValueError):
    pass


class SeriesPoint(BaseModel):
    start: str
    value: float | None
    n: int
    expected: int
    coverage: float
    partial: bool
    insufficient: bool
    reference: float | None = None


class SeriesResponse(BaseModel):
    dataset: str
    dataset_name: str
    variable: str
    variable_label: str
    unit: str
    kind: str
    location: str | None
    grain: str
    agg: str
    start: str
    end: str
    compare: str | None
    reference_label: str | None
    reference_kind: str | None
    points: list[SeriesPoint]
    source: str | None
    attribution: str | None
    caveats: list[str]


def _agg(name: str, column: Any) -> Any:
    if name == "sum":
        return func.sum(column)
    if name == "mean":
        return func.avg(column)
    if name == "min":
        return func.min(column)
    if name == "max":
        return func.max(column)
    return func.count(column)


def _validate(ds_id: str, variable: str, grain: str, agg: str) -> tuple[Dataset, Variable]:
    ds = DATASETS.get(ds_id)
    if ds is None:
        raise SeriesError(f"conjunto desconhecido: {ds_id}")
    var = ds.variable(variable)
    error = aggregation_error(ds, variable, agg) or grain_error(ds, grain)
    if error or var is None:
        raise SeriesError(error or "variável desconhecida")
    return ds, var


def _resolution(ds: Dataset) -> Resolution:
    if ds.resolution == "month":
        return "month"
    if ds.resolution == "hour":
        return "hour"
    return "day"


async def _raw_buckets(
    session: AsyncSession,
    ds: Dataset,
    variable: str,
    location: str | None,
    start: date,
    end: date,
    grain: Grain,
    agg: str,
) -> dict[date, tuple[float | None, int]]:
    """Período -> (valor agregado, quantidade de valores)."""
    if ds.id == "iag-rain-monthly":
        m = rain_monthly_observed
        month_day = func.make_date(cast(m.c.year, Integer), cast(m.c.month, Integer), 1)
        bucket = cast(func.date_trunc(grain, month_day), Date)
        stmt = (
            select(bucket, _agg(agg, m.c.value_mm), func.count())
            .where(month_day >= bucket_start(start, "month"), month_day <= end)
            .group_by(bucket)
        )
    elif ds.id == "reanalysis-daily":
        if location is None:
            raise SeriesError("informe o ponto (location) da reanálise")
        c = climate_daily
        bucket = cast(func.date_trunc(grain, c.c.day), Date)
        stmt = (
            select(bucket, _agg(agg, c.c.value), func.count())
            .where(
                c.c.point_key == location,
                c.c.variable == variable,
                c.c.day >= start,
                c.c.day <= end,
            )
            .group_by(bucket)
        )
    elif ds.id == "forecast-hourly":
        if location is None:
            raise SeriesError("informe o ponto (location) da previsão")
        f = weather_forecasts
        local = func.timezone("America/Sao_Paulo", f.c.valid_at)
        bucket = cast(func.date_trunc("day", local), Date)
        start_dt = datetime(start.year, start.month, start.day, tzinfo=LOCAL_TZ)
        end_dt = datetime(end.year, end.month, end.day, tzinfo=LOCAL_TZ) + timedelta(days=1)
        stmt = (
            select(bucket, _agg(agg, f.c.value), func.count())
            .where(
                f.c.point_key == location,
                f.c.resolution == "hourly",
                f.c.variable == variable,
                f.c.valid_at >= start_dt,
                f.c.valid_at < end_dt,
            )
            .group_by(bucket)
        )
    elif ds.id == "flood-occurrences":
        o = flood_occurrences
        bucket = cast(func.date_trunc(grain, o.c.occurred_on), Date)
        conditions = [o.c.occurred_on >= start, o.c.occurred_on <= end]
        if location:
            conditions.append(o.c.subprefecture == location)
        stmt = select(bucket, func.count(), func.count()).where(*conditions).group_by(bucket)
    elif ds.id == "risk-assessments":
        if location not in CATEGORIES:
            raise SeriesError("informe a categoria (location): " + ", ".join(CATEGORIES))
        a, r = risk_assessments, risk_runs
        per_run = (
            select(
                r.c.computed_at.label("at"),
                func.count(a.c.id).filter(a.c.category == location).label("n"),
            )
            .join(a, a.c.run_id == r.c.id)
            .where(
                r.c.status == "SUCCESS",
                r.c.computed_at >= datetime(start.year, start.month, start.day, tzinfo=LOCAL_TZ),
                r.c.computed_at
                < datetime(end.year, end.month, end.day, tzinfo=LOCAL_TZ) + timedelta(days=1),
            )
            .group_by(r.c.id, r.c.computed_at)
            .subquery()
        )
        bucket = cast(
            func.date_trunc("day", func.timezone("America/Sao_Paulo", per_run.c.at)), Date
        )
        stmt = select(bucket, _agg(agg, per_run.c.n), func.count()).group_by(bucket)
    else:  # coletas
        i = ingestion_runs
        local = func.timezone("America/Sao_Paulo", i.c.started_at)
        bucket = cast(func.date_trunc("day", local), Date)
        conditions = [
            i.c.started_at >= datetime(start.year, start.month, start.day, tzinfo=LOCAL_TZ),
            i.c.started_at
            < datetime(end.year, end.month, end.day, tzinfo=LOCAL_TZ) + timedelta(days=1),
        ]
        if location:
            source_id = select(data_sources.c.id).where(data_sources.c.code == location)
            conditions.append(i.c.source_id.in_(source_id.scalar_subquery()))
        value = (
            func.count()
            if variable == "runs"
            else _agg(agg, extract("epoch", i.c.finished_at - i.c.started_at))
        )
        stmt = select(bucket, value, func.count()).where(*conditions).group_by(bucket)
    rows = await session.execute(stmt)
    return {r[0]: (float(r[1]) if r[1] is not None else None, int(r[2])) for r in rows}


def _complete_coverage(ds: Dataset) -> bool:
    """Contagens de eventos e execuções não têm "valores esperados": cobertura = 1."""
    return ds.id in ("flood-occurrences", "risk-assessments", "ingestion-runs")


async def _series_points(
    session: AsyncSession,
    ds: Dataset,
    variable: str,
    location: str | None,
    start: date,
    end: date,
    grain: Grain,
    agg: str,
) -> list[SeriesPoint]:
    raw = await _raw_buckets(session, ds, variable, location, start, end, grain, agg)
    # Previsão, risco e coletas são agrupados por dia local no SQL.
    effective_grain: Grain = "day" if ds.id in DAILY_ONLY else grain
    starts = buckets(start, end, effective_grain)
    if len(starts) > MAX_POINTS:
        raise SeriesError(f"período longo demais para esse agrupamento (máx. {MAX_POINTS} pontos)")
    points: list[SeriesPoint] = []
    for b in starts:
        value, n = raw.get(b, (None, 0))
        if _complete_coverage(ds):
            value = value if value is not None else (0.0 if agg in ("count", "sum") else None)
            expected = n
            final = finalize(value, 1, 1)
        else:
            expected = expected_count(b, effective_grain, _resolution(ds), start, end)
            final = finalize(value, n, expected)
        points.append(
            SeriesPoint(
                start=b.isoformat(),
                value=final.value,
                n=n,
                expected=expected,
                coverage=final.coverage,
                partial=final.partial,
                insufficient=final.insufficient,
            )
        )
    return points


async def _normal_reference(
    session: AsyncSession,
    ds: Dataset,
    variable: str,
    location: str | None,
    grain: Grain,
    agg: str,
) -> dict[int, float]:
    """Normal 1991–2020 por mês (1–12) ou anual (chave 0), com o mesmo tipo de agregação."""
    if grain not in ("month", "year"):
        raise SeriesError("comparação com a normal disponível para agrupamento mensal ou anual")
    if ds.id == "iag-rain-monthly":
        m = rain_monthly_observed
        rows = await session.execute(
            select(m.c.year, m.c.month, m.c.value_mm).where(
                m.c.year >= NORMAL_START, m.c.year <= NORMAL_END
            )
        )
        monthly = {(int(r.year), int(r.month)): float(r.value_mm) for r in rows}
    elif ds.id == "reanalysis-daily":
        c = climate_daily
        year = cast(extract("year", c.c.day), Integer)
        month = cast(extract("month", c.c.day), Integer)
        rows = await session.execute(
            select(year, month, _agg(agg, c.c.value), func.count())
            .where(
                c.c.point_key == location,
                c.c.variable == variable,
                year >= NORMAL_START,
                year <= NORMAL_END,
            )
            .group_by(year, month)
        )
        monthly = {
            (int(y), int(mo)): float(v)
            for y, mo, v, n in rows
            if int(n) == calendar.monthrange(int(y), int(mo))[1]
        }
    else:
        raise SeriesError(f"{ds.name}: sem normal climatológica")
    normals = monthly_normals(monthly)
    if grain == "month":
        return {month: n.mean for month, n in normals.items()}
    if len(normals) < 12:
        return {}
    if agg == "sum":
        return {0: sum(n.mean for n in normals.values())}
    if agg == "mean":
        return {0: sum(n.mean for n in normals.values()) / 12}
    if agg == "max":
        return {0: max(n.mean for n in normals.values())}
    return {0: min(n.mean for n in normals.values())}


async def get_series(
    session: AsyncSession,
    *,
    dataset: str,
    variable: str,
    location: str | None,
    start: date,
    end: date,
    grain: Grain,
    agg: str,
    compare: CompareMode | None,
    now: datetime,
) -> SeriesResponse:
    if end < start:
        raise SeriesError("fim antes do início")
    ds, var = _validate(dataset, variable, grain, agg)
    points = await _series_points(session, ds, variable, location, start, end, grain, agg)
    reference_label: str | None = None
    reference_kind: str | None = None
    if compare == "normal":
        normal = await _normal_reference(session, ds, variable, location, grain, agg)
        for p in points:
            key = 0 if grain == "year" else date.fromisoformat(p.start).month
            p.reference = normal.get(key)
        reference_label = f"Normal {NORMAL_START}–{NORMAL_END} ({_kind_word(ds.kind)})"
        reference_kind = ds.kind
    elif compare in ("previous_period", "same_period_last_year"):
        s2, e2 = shifted_window(start, end, compare)
        other = await _series_points(session, ds, variable, location, s2, e2, grain, agg)
        for p, q in zip(points, other, strict=False):
            p.reference = q.value
        reference_label = (
            f"Período anterior ({s2:%d/%m/%Y}–{e2:%d/%m/%Y})"
            if compare == "previous_period"
            else f"Mesmo período do ano anterior ({s2:%d/%m/%Y}–{e2:%d/%m/%Y})"
        )
        reference_kind = ds.kind
    statuses = {s.code: s for s in await list_source_status(session, now=now, credentials={})}
    source = statuses.get(ds.source_code)
    return SeriesResponse(
        dataset=ds.id,
        dataset_name=ds.name,
        variable=var.code,
        variable_label=var.label,
        unit=var.unit,
        kind=ds.kind,
        location=location,
        grain=grain,
        agg=agg,
        start=start.isoformat(),
        end=end.isoformat(),
        compare=compare,
        reference_label=reference_label,
        reference_kind=reference_kind,
        points=points,
        source=source.name if source else None,
        attribution=source.attribution if source else None,
        caveats=list(ds.caveats),
    )


def _kind_word(kind: str) -> str:
    return {"OBSERVED": "medida", "MODELED": "reanálise", "FORECAST": "previsão"}.get(
        kind, "calculada"
    )


def series_csv(series: SeriesResponse, generated_at: datetime) -> str:
    """CSV UTF-8 com cabeçalho de metadados em linhas iniciadas por '#' (FR-089, AC-087)."""
    out = io.StringIO()
    meta = [
        ("conjunto", series.dataset_name),
        ("variavel", f"{series.variable_label} ({series.unit})"),
        ("tipo", series.kind),
        ("local", series.location or "—"),
        ("periodo", f"{series.start} a {series.end}"),
        ("agrupamento", f"{series.grain}, {series.agg}"),
        ("comparacao", series.reference_label or "—"),
        ("fonte", series.source or "—"),
        ("atribuicao", series.attribution or "—"),
        ("gerado_em", generated_at.astimezone(UTC).isoformat()),
    ]
    for key, value in meta:
        out.write(f"# {key}: {value}\n")
    for caveat in series.caveats:
        out.write(f"# aviso: {caveat}\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        ["inicio", "valor", "unidade", "referencia", "n", "esperado", "cobertura", "parcial"]
    )
    for p in series.points:
        writer.writerow(
            [
                p.start,
                "" if p.value is None else round(p.value, 3),
                series.unit,
                "" if p.reference is None else round(p.reference, 3),
                p.n,
                p.expected,
                p.coverage,
                "sim" if p.partial else ("insuficiente" if p.insufficient else "não"),
            ]
        )
    return out.getvalue()


# --- climatologia mensal (FR-088) ------------------------------------------------------------


class MonthClimate(BaseModel):
    month: int
    mean: float | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None
    years_used: int


class ClimatologyResponse(BaseModel):
    dataset: str
    variable: str
    unit: str
    kind: str
    location: str | None
    period: str
    months: list[MonthClimate]
    annual_mean: float | None
    published: list[float] | None = None
    published_annual: float | None = None


async def _monthly_values(
    session: AsyncSession, ds: Dataset, variable: str, location: str | None, agg: str
) -> dict[tuple[int, int], float]:
    if ds.id == "iag-rain-monthly":
        m = rain_monthly_observed
        rows = await session.execute(select(m.c.year, m.c.month, m.c.value_mm))
        return {(int(r.year), int(r.month)): float(r.value_mm) for r in rows}
    if ds.id != "reanalysis-daily":
        raise SeriesError(f"{ds.name}: sem climatologia")
    c = climate_daily
    year = cast(extract("year", c.c.day), Integer)
    month = cast(extract("month", c.c.day), Integer)
    rows = await session.execute(
        select(year, month, _agg(agg, c.c.value), func.count())
        .where(c.c.point_key == location, c.c.variable == variable)
        .group_by(year, month)
    )
    return {
        (int(y), int(mo)): float(v)
        for y, mo, v, n in rows
        if int(n) == calendar.monthrange(int(y), int(mo))[1]
    }


async def get_climatology(
    session: AsyncSession,
    *,
    dataset: str,
    variable: str,
    location: str | None,
    start_year: int,
    end_year: int,
) -> ClimatologyResponse:
    ds = DATASETS.get(dataset)
    var = ds.variable(variable) if ds else None
    if ds is None or var is None:
        raise SeriesError("conjunto ou variável desconhecida")
    agg = var.default_agg
    monthly = await _monthly_values(session, ds, variable, location, agg)
    months: list[MonthClimate] = []
    for month in range(1, 13):
        values = sorted(
            v for (y, mo), v in monthly.items() if mo == month and start_year <= y <= end_year
        )
        enough = len(values) >= 25
        months.append(
            MonthClimate(
                month=month,
                mean=sum(values) / len(values) if enough else None,
                p10=percentile(values, 10) if enough else None,
                p25=percentile(values, 25) if enough else None,
                p75=percentile(values, 75) if enough else None,
                p90=percentile(values, 90) if enough else None,
                years_used=len(values),
            )
        )
    means = [m.mean for m in months]
    annual = None
    if all(v is not None for v in means):
        total = sum(v for v in means if v is not None)
        annual = total if agg == "sum" else total / 12
    response = ClimatologyResponse(
        dataset=ds.id,
        variable=variable,
        unit=var.unit,
        kind=ds.kind,
        location=location,
        period=f"{start_year}-{end_year}",
        months=months,
        annual_mean=annual,
    )
    if ds.id == "iag-rain-monthly":
        n = published_normals
        rows = await session.execute(
            select(n.c.month, n.c.value_mm).where(n.c.period == f"{start_year}-{end_year}")
        )
        published = {int(r.month): float(r.value_mm) for r in rows}
        if len(published) == 13:
            response.published = [published[m] for m in range(1, 13)]
            response.published_annual = published[0]
    return response


# --- distribuição e extremos (FR-090) --------------------------------------------------------


class Bin(BaseModel):
    low: float
    high: float
    count: int


class Extreme(BaseModel):
    day: str
    value: float


class DistributionResponse(BaseModel):
    dataset: str
    variable: str
    unit: str
    kind: str
    location: str
    start: str
    end: str
    days: int
    wet_days: int
    threshold: float
    bins: list[Bin]
    extremes: list[Extreme]


RAIN_EDGES = (1.0, 5.0, 10.0, 20.0, 30.0, 50.0, 80.0, 1000.0)


async def get_distribution(
    session: AsyncSession, *, location: str, start: date, end: date
) -> DistributionResponse:
    """Distribuição dos dias de chuva (≥ 1 mm) e 10 maiores chuvas diárias (reanálise)."""
    c = climate_daily
    rows = await session.execute(
        select(c.c.day, c.c.value).where(
            c.c.point_key == location,
            c.c.variable == "precipitation_sum",
            c.c.day >= start,
            c.c.day <= end,
        )
    )
    values = [(r.day, float(r.value)) for r in rows]
    wet = [v for _, v in values if v >= RAIN_EDGES[0]]
    counts = histogram(wet, RAIN_EDGES)
    top = sorted(values, key=lambda item: item[1], reverse=True)[:10]
    return DistributionResponse(
        dataset="reanalysis-daily",
        variable="precipitation_sum",
        unit="mm",
        kind="MODELED",
        location=location,
        start=start.isoformat(),
        end=end.isoformat(),
        days=len(values),
        wet_days=len(wet),
        threshold=RAIN_EDGES[0],
        bins=[
            Bin(low=RAIN_EDGES[i], high=RAIN_EDGES[i + 1], count=counts[i])
            for i in range(len(counts))
        ],
        extremes=[Extreme(day=d.isoformat(), value=v) for d, v in top],
    )


# --- ranking por local (FR-094) --------------------------------------------------------------


class RankItem(BaseModel):
    key: str
    value: float
    n: int


class RankingResponse(BaseModel):
    dataset: str
    variable: str
    unit: str
    kind: str
    agg: str
    start: str
    end: str
    items: list[RankItem]


async def get_ranking(
    session: AsyncSession, *, dataset: str, variable: str, agg: str, start: date, end: date
) -> RankingResponse:
    ds, var = _validate(dataset, variable, "day" if dataset != "iag-rain-monthly" else "month", agg)
    if dataset == "reanalysis-daily":
        c = climate_daily
        rows = await session.execute(
            select(c.c.point_key, _agg(agg, c.c.value), func.count())
            .where(c.c.variable == variable, c.c.day >= start, c.c.day <= end)
            .group_by(c.c.point_key)
        )
    elif dataset == "flood-occurrences":
        o = flood_occurrences
        rows = await session.execute(
            select(o.c.subprefecture, func.count(), func.count())
            .where(o.c.occurred_on >= start, o.c.occurred_on <= end, o.c.subprefecture.is_not(None))
            .group_by(o.c.subprefecture)
        )
    else:
        raise SeriesError(f"{ds.name}: ranking por local indisponível")
    items = sorted(
        (RankItem(key=str(k), value=float(v), n=int(n)) for k, v, n in rows if v is not None),
        key=lambda item: item.value,
        reverse=True,
    )
    return RankingResponse(
        dataset=ds.id,
        variable=var.code,
        unit=var.unit,
        kind=ds.kind,
        agg=agg,
        start=start.isoformat(),
        end=end.isoformat(),
        items=items,
    )


# --- tendências históricas (FR-091) ----------------------------------------------------------


class YearValue(BaseModel):
    year: int
    value: float


class NormalComparison(BaseModel):
    period: str
    computed: float
    published: float | None
    difference: float | None


class TrendsResponse(BaseModel):
    station: str
    unit: str
    kind: str
    annual: list[YearValue]
    moving_average_10y: list[YearValue]
    normals: list[NormalComparison]
    wettest: list[YearValue]
    driest: list[YearValue]
    note: str
    attribution: str | None


NORMAL_PERIODS = ((1933, 1960), (1961, 1990), (1991, 2020))
TRENDS_NOTE = (
    "Variação entre normais e médias móveis descreve a série; sozinha, não indica a causa. "
    "Uma estação representa a zona sul (Água Funda), não a cidade inteira."
)


async def get_trends(session: AsyncSession, now: datetime) -> TrendsResponse:
    m = rain_monthly_observed
    rows = await session.execute(select(m.c.station_code, m.c.year, m.c.month, m.c.value_mm))
    monthly: dict[tuple[int, int], float] = {}
    station = ""
    for r in rows:
        station = str(r.station_code)
        monthly[(int(r.year), int(r.month))] = float(r.value_mm)
    annual = annual_totals(monthly)
    series = sorted(annual.items())
    n = published_normals
    published_rows = await session.execute(select(n.c.period, n.c.value_mm).where(n.c.month == 0))
    published = {str(r.period): float(r.value_mm) for r in published_rows}
    normals: list[NormalComparison] = []
    for start_year, end_year in NORMAL_PERIODS:
        normal = monthly_normals(monthly, start_year, end_year, min_years=25)
        if len(normal) == 12:
            computed = sum(v.mean for v in normal.values())
            key = f"{start_year}-{end_year}"
            pub = published.get(key)
            normals.append(
                NormalComparison(
                    period=key,
                    computed=round(computed, 1),
                    published=pub,
                    difference=round(computed - pub, 1) if pub is not None else None,
                )
            )
    ranked = sorted(series, key=lambda item: item[1])
    statuses = {s.code: s for s in await list_source_status(session, now=now, credentials={})}
    source = statuses.get("iag-usp-rain-monthly")
    return TrendsResponse(
        station=station,
        unit="mm",
        kind="OBSERVED",
        annual=[YearValue(year=y, value=round(v, 1)) for y, v in series],
        moving_average_10y=[
            YearValue(year=y, value=round(v, 1)) for y, v in moving_average(series, 10)
        ],
        normals=normals,
        wettest=[YearValue(year=y, value=round(v, 1)) for y, v in reversed(ranked[-5:])],
        driest=[YearValue(year=y, value=round(v, 1)) for y, v in ranked[:5]],
        note=TRENDS_NOTE,
        attribution=source.attribution if source else None,
    )


# --- histórico do risco (FR-092) -------------------------------------------------------------


class RunCounts(BaseModel):
    computed_at: datetime
    counts: dict[str, int]


class GroupCounts(BaseModel):
    name: str
    counts: dict[str, int]
    total: int


class RiskHistoryResponse(BaseModel):
    runs: list[RunCounts]
    by_subprefecture: list[GroupCounts]
    by_basin: list[GroupCounts]
    engine_note: str = "Estimativa experimental do sistema — não é alerta oficial."


async def get_risk_history(session: AsyncSession, now: datetime, days: int) -> RiskHistoryResponse:
    a, r, s = risk_assessments, risk_runs, hydro_risk_sectors
    rows = await session.execute(
        select(r.c.id, r.c.computed_at, a.c.category, func.count())
        .join(a, a.c.run_id == r.c.id)
        .where(r.c.status == "SUCCESS", r.c.computed_at >= now - timedelta(days=days))
        .group_by(r.c.id, r.c.computed_at, a.c.category)
        .order_by(r.c.computed_at)
    )
    by_run: dict[int, RunCounts] = {}
    for run_id, at, category, n in rows:
        item = by_run.setdefault(
            int(run_id), RunCounts(computed_at=at, counts=dict.fromkeys(CATEGORIES, 0))
        )
        item.counts[str(category)] = int(n)
    latest = (
        await session.execute(
            select(r.c.id).where(r.c.status == "SUCCESS").order_by(r.c.computed_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    async def grouped(column: Any) -> list[GroupCounts]:
        if latest is None:
            return []
        result = await session.execute(
            select(column, a.c.category, func.count())
            .join(a, a.c.sector_id == s.c.id)
            .where(a.c.run_id == latest, column.is_not(None))
            .group_by(column, a.c.category)
        )
        groups: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(CATEGORIES, 0))
        for name, category, n in result:
            groups[str(name)][str(category)] = int(n)
        ordered = sorted(
            groups.items(),
            key=lambda item: (
                -(item[1]["CRITICAL"] * 1000 + item[1]["HIGH"] * 100 + item[1]["MODERATE"]),
                -sum(item[1].values()),
                item[0],
            ),
        )
        return [GroupCounts(name=k, counts=v, total=sum(v.values())) for k, v in ordered]

    return RiskHistoryResponse(
        runs=list(by_run.values()),
        by_subprefecture=await grouped(s.c.subprefecture),
        by_basin=await grouped(s.c.basin),
    )


# --- saúde das fontes (FR-093) ---------------------------------------------------------------


class SourceHealth(BaseModel):
    code: str
    name: str
    freshness: str
    reason: str
    last_success_at: datetime | None
    age_hours: float | None
    expected_interval_h: float
    runs_7d: int
    success_7d: int
    availability_7d: float | None
    runs_30d: int
    success_30d: int
    availability_30d: float | None
    mean_duration_s: float | None
    rejected_rate: float | None
    last_failure_at: datetime | None
    last_failure: str | None
    coverage: str | None


async def _coverage_texts(session: AsyncSession) -> dict[str, str]:
    texts: dict[str, str] = {}
    points = (
        await session.execute(select(func.count(func.distinct(weather_forecasts.c.point_key))))
    ).scalar_one()
    texts["open-meteo-forecast"] = f"{points} pontos de previsão"
    archive = (
        await session.execute(select(func.count(func.distinct(climate_daily.c.point_key))))
    ).scalar_one()
    texts["open-meteo-archive"] = f"{archive} pontos com série desde 1991"
    sectors = (
        await session.execute(
            select(func.count())
            .select_from(hydro_risk_sectors)
            .where(hydro_risk_sectors.c.active.is_(True))
        )
    ).scalar_one()
    texts["geosampa-risk-sectors"] = f"{sectors} setores ativos"
    texts["flood-risk-engine"] = f"{sectors} setores avaliados por execução"
    years = (
        await session.execute(select(func.count(func.distinct(rain_monthly_observed.c.year))))
    ).scalar_one()
    texts["iag-usp-rain-monthly"] = f"{years} anos completos"
    occurrences = (
        await session.execute(select(func.count()).select_from(flood_occurrences))
    ).scalar_one()
    texts["geosampa-flood-occurrences"] = f"{occurrences} ocorrências"
    return texts


async def get_sources_health(
    session: AsyncSession, now: datetime, credentials: dict[str, bool]
) -> list[SourceHealth]:
    statuses = await list_source_status(session, now=now, credentials=credentials)
    i = ingestion_runs
    ok = case((i.c.status.in_(("SUCCESS", "PARTIAL")), 1), else_=0)

    async def window(days: int) -> dict[int, tuple[int, int]]:
        rows = await session.execute(
            select(i.c.source_id, func.count(), func.sum(ok))
            .where(i.c.started_at >= now - timedelta(days=days))
            .group_by(i.c.source_id)
        )
        return {int(sid): (int(total), int(success or 0)) for sid, total, success in rows}

    w7, w30 = await window(7), await window(30)
    stats = await session.execute(
        select(
            i.c.source_id,
            func.avg(extract("epoch", i.c.finished_at - i.c.started_at)),
            func.sum(i.c.records_rejected),
            func.sum(i.c.records_received),
        )
        .where(i.c.started_at >= now - timedelta(days=30))
        .group_by(i.c.source_id)
    )
    by_source = {int(r[0]): r for r in stats}
    last_failures = await session.execute(
        select(i.c.source_id, i.c.started_at, i.c.error_summary)
        .where(i.c.status == "FAILED")
        .order_by(i.c.source_id, i.c.started_at.desc())
        .distinct(i.c.source_id)
    )
    failures = {int(r[0]): (r[1], r[2]) for r in last_failures}
    ids = {
        str(code): int(sid)
        for code, sid in await session.execute(select(data_sources.c.code, data_sources.c.id))
    }
    coverage = await _coverage_texts(session)
    result: list[SourceHealth] = []
    for s in statuses:
        sid = ids.get(s.code, -1)
        t7, s7 = w7.get(sid, (0, 0))
        t30, s30 = w30.get(sid, (0, 0))
        row = by_source.get(sid)
        received = float(row[3]) if row is not None and row[3] else 0.0
        failure = failures.get(sid)
        result.append(
            SourceHealth(
                code=s.code,
                name=s.name,
                freshness=s.freshness,
                reason=s.reason,
                last_success_at=s.last_success_at,
                age_hours=round((now - s.last_success_at).total_seconds() / 3600, 2)
                if s.last_success_at
                else None,
                expected_interval_h=round(s.expected_interval_s / 3600, 2),
                runs_7d=t7,
                success_7d=s7,
                availability_7d=round(s7 / t7, 4) if t7 else None,
                runs_30d=t30,
                success_30d=s30,
                availability_30d=round(s30 / t30, 4) if t30 else None,
                mean_duration_s=round(float(row[1]), 2) if row is not None and row[1] else None,
                rejected_rate=(
                    round(float(row[2] or 0) / received, 4)
                    if row is not None and received
                    else None
                ),
                last_failure_at=failure[0] if failure else None,
                last_failure=failure[1] if failure else None,
                coverage=coverage.get(s.code),
            )
        )
    return result

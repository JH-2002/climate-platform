"""Análises (spec 006, Parte A): catálogo, estatísticas, KPIs e insights.

Agrega no PostgreSQL e usa o motor puro (`app.analytics`) para regras e climatologia.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import Integer, cast, distinct, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.catalog import DATASETS, Dataset
from app.analytics.climatology import (
    NORMAL_END,
    NORMAL_START,
    PeriodComparison,
    current_dry_spell,
    max_dry_spells_by_year,
)
from app.analytics.places import CITY_CENTER, region_label
from app.analytics.rules import (
    INSIGHT_RULES_VERSION,
    Insight,
    fmt,
    in01_heavy_forecast,
    in02_month_to_date,
    in03_dry_spell,
    in04_risk_increase,
    in05_source_problem,
    in06_occurrence_concentration,
)
from app.analytics.stats import Description, describe
from app.models.tables import (
    climate_daily,
    flood_occurrences,
    hydro_risk_sectors,
    ingestion_runs,
    rain_monthly_observed,
    risk_assessments,
    risk_runs,
    weather_forecasts,
)
from app.services.forecast import FORECAST_SOURCE, current_hour
from app.services.risk import (
    ForecastPoint,
    forecast_points,
    haversine_km,
    hourly_precipitation_by_point,
    rain_inputs,
)
from app.services.sources import SourceStatus, list_source_status

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
ARCHIVE_SOURCE = "open-meteo-archive"
IAG_SOURCE = "iag-usp-rain-monthly"
RAIN = "precipitation_sum"
# Ponto da reanálise usado para um ponto de previsão: o mais próximo até esta distância.
MATCH_KM = 15.0
RISK_CATEGORY_LABELS = {
    "CRITICAL": "Crítico",
    "HIGH": "Alto",
    "MODERATE": "Moderado",
    "LOW": "Baixo",
    "UNKNOWN": "Desconhecido",
}


def local_today(now: datetime) -> date:
    return now.astimezone(LOCAL_TZ).date()


# --- catálogo (FR-082) -----------------------------------------------------------------------


class VariableInfo(BaseModel):
    code: str
    label: str
    unit: str
    aggregations: list[str]


class LocationInfo(BaseModel):
    key: str
    label: str
    latitude: float | None = None
    longitude: float | None = None
    detail: str | None = None


class DatasetInfo(BaseModel):
    id: str
    name: str
    description: str
    kind: str
    resolution: str
    spatial: str
    source_code: str
    source_name: str | None
    attribution: str | None
    license: str | None
    freshness: str | None
    variables: list[VariableInfo]
    grains: list[str]
    visualizations: list[str]
    numeric: bool
    caveats: list[str]
    records: int
    period_start: str | None
    period_end: str | None
    locations: list[LocationInfo]


def _base_info(ds: Dataset, status: dict[str, SourceStatus], **extra: Any) -> DatasetInfo:
    source = status.get(ds.source_code)
    return DatasetInfo(
        id=ds.id,
        name=ds.name,
        description=ds.description,
        kind=ds.kind,
        resolution=ds.resolution,
        spatial=ds.spatial,
        source_code=ds.source_code,
        source_name=source.name if source else None,
        attribution=source.attribution if source else None,
        license=source.license if source else None,
        freshness=source.freshness if source else None,
        variables=[
            VariableInfo(code=v.code, label=v.label, unit=v.unit, aggregations=list(v.aggregations))
            for v in ds.variables
        ],
        grains=list(ds.grains),
        visualizations=list(ds.visualizations),
        numeric=ds.numeric,
        caveats=list(ds.caveats),
        **extra,
    )


def year_month(year: Any, month: Any) -> Any:
    """AAAAMM como inteiro (as colunas são smallint: a conta estouraria o tipo)."""
    return cast(year, Integer) * 100 + cast(month, Integer)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


async def archive_points(session: AsyncSession) -> list[LocationInfo]:
    t = climate_daily
    rows = await session.execute(
        select(
            t.c.point_key,
            func.ST_Y(func.geometry(t.c.point)).label("lat"),
            func.ST_X(func.geometry(t.c.point)).label("lon"),
            func.max(t.c.cell_key).label("cell"),
        )
        .group_by(t.c.point_key, t.c.point)
        .order_by(t.c.point_key)
    )
    return [
        LocationInfo(
            key=r.point_key,
            label=region_label(float(r.lat), float(r.lon)),
            latitude=float(r.lat),
            longitude=float(r.lon),
            detail=f"célula do modelo {r.cell}",
        )
        for r in rows
    ]


async def list_datasets(
    session: AsyncSession, now: datetime, credentials: dict[str, bool]
) -> list[DatasetInfo]:
    status = {
        s.code: s for s in await list_source_status(session, now=now, credentials=credentials)
    }
    infos: list[DatasetInfo] = []

    m = rain_monthly_observed
    iag = (
        await session.execute(
            select(
                func.count(),
                func.min(year_month(m.c.year, m.c.month)),
                func.max(year_month(m.c.year, m.c.month)),
                func.max(m.c.station_code),
            )
        )
    ).one()
    infos.append(
        _base_info(
            DATASETS["iag-rain-monthly"],
            status,
            records=int(iag[0]),
            period_start=f"{iag[1] // 100}-{iag[1] % 100:02d}" if iag[1] else None,
            period_end=f"{iag[2] // 100}-{iag[2] % 100:02d}" if iag[2] else None,
            locations=[
                LocationInfo(
                    key=str(iag[3]),
                    label="IAG/USP — Água Funda",
                    latitude=-23.6512,
                    longitude=-46.6224,
                )
            ]
            if iag[3]
            else [],
        )
    )

    c = climate_daily
    arch = (await session.execute(select(func.count(), func.min(c.c.day), func.max(c.c.day)))).one()
    infos.append(
        _base_info(
            DATASETS["reanalysis-daily"],
            status,
            records=int(arch[0]),
            period_start=_iso(arch[1]),
            period_end=_iso(arch[2]),
            locations=await archive_points(session),
        )
    )

    f = weather_forecasts
    fc = (
        await session.execute(
            select(func.count(), func.min(f.c.valid_at), func.max(f.c.valid_at)).where(
                f.c.resolution == "hourly"
            )
        )
    ).one()
    points = await forecast_points(session)
    infos.append(
        _base_info(
            DATASETS["forecast-hourly"],
            status,
            records=int(fc[0]),
            period_start=_iso(fc[1]),
            period_end=_iso(fc[2]),
            locations=[
                LocationInfo(
                    key=p.point_key,
                    label=region_label(p.latitude, p.longitude),
                    latitude=p.latitude,
                    longitude=p.longitude,
                )
                for p in points
            ],
        )
    )

    o = flood_occurrences
    occ = (
        await session.execute(
            select(
                func.count(),
                func.min(o.c.occurred_on),
                func.max(o.c.occurred_on),
                func.count(distinct(o.c.subprefecture)),
            )
        )
    ).one()
    infos.append(
        _base_info(
            DATASETS["flood-occurrences"],
            status,
            records=int(occ[0]),
            period_start=_iso(occ[1]),
            period_end=_iso(occ[2]),
            locations=[
                LocationInfo(key=name, label=name.title())
                for (name,) in (
                    await session.execute(
                        select(o.c.subprefecture)
                        .where(o.c.subprefecture.is_not(None))
                        .distinct()
                        .order_by(o.c.subprefecture)
                    )
                ).tuples()
            ],
        )
    )

    r = risk_runs
    runs = (
        await session.execute(
            select(func.count(), func.min(r.c.computed_at), func.max(r.c.computed_at)).where(
                r.c.status == "SUCCESS"
            )
        )
    ).one()
    sectors = (
        await session.execute(
            select(func.count())
            .select_from(hydro_risk_sectors)
            .where(hydro_risk_sectors.c.active.is_(True))
        )
    ).scalar_one()
    infos.append(
        _base_info(
            DATASETS["risk-assessments"],
            status,
            records=int(runs[0]),
            period_start=_iso(runs[1]),
            period_end=_iso(runs[2]),
            locations=[
                LocationInfo(key=code, label=label, detail=f"{sectors} setores ativos")
                for code, label in RISK_CATEGORY_LABELS.items()
            ],
        )
    )

    i = ingestion_runs
    ing = (
        await session.execute(
            select(func.count(), func.min(i.c.started_at), func.max(i.c.started_at))
        )
    ).one()
    infos.append(
        _base_info(
            DATASETS["ingestion-runs"],
            status,
            records=int(ing[0]),
            period_start=_iso(ing[1]),
            period_end=_iso(ing[2]),
            locations=[LocationInfo(key=s.code, label=s.name) for s in status.values()],
        )
    )
    return infos


# --- estatísticas (FR-083) -------------------------------------------------------------------


class DescribeResult(BaseModel):
    dataset: str
    variable: str
    unit: str
    kind: str
    location: str | None
    start: str
    end: str
    expected: int
    n: int
    missing: int
    coverage: float
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    std: float | None
    p5: float | None
    p25: float | None
    p75: float | None
    p95: float | None
    outlier_count: int
    outliers: list[float]
    method: str = "Percentis por interpolação linear; atípicos fora de 1,5 × IQR."


class DescribeError(ValueError):
    pass


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    months = []
    y, mth = start.year, start.month
    while (y, mth) <= (end.year, end.month):
        months.append((y, mth))
        y, mth = (y + 1, 1) if mth == 12 else (y, mth + 1)
    return months


async def describe_dataset(
    session: AsyncSession,
    dataset_id: str,
    variable: str,
    location: str | None,
    start: date,
    end: date,
) -> DescribeResult:
    ds = DATASETS.get(dataset_id)
    if ds is None:
        raise DescribeError(f"conjunto desconhecido: {dataset_id}")
    var = ds.variable(variable)
    if var is None:
        raise DescribeError(f"variável desconhecida em {dataset_id}: {variable}")
    if not ds.numeric:
        raise DescribeError(f"{ds.name}: estatísticas descritivas só para séries numéricas")
    if end < start:
        raise DescribeError("fim antes do início")

    values: list[float | None]
    if dataset_id == "iag-rain-monthly":
        m = rain_monthly_observed
        rows = await session.execute(
            select(m.c.year, m.c.month, m.c.value_mm).where(
                year_month(m.c.year, m.c.month) >= start.year * 100 + start.month,
                year_month(m.c.year, m.c.month) <= end.year * 100 + end.month,
            )
        )
        found = {(r.year, r.month): float(r.value_mm) for r in rows}
        expected_keys = _months_between(start, end)
        values = [found.get(k) for k in expected_keys]
    elif dataset_id == "reanalysis-daily":
        if location is None:
            raise DescribeError("informe o ponto (location) da reanálise")
        c = climate_daily
        rows = await session.execute(
            select(c.c.day, c.c.value).where(
                c.c.point_key == location,
                c.c.variable == variable,
                c.c.day >= start,
                c.c.day <= end,
            )
        )
        found_days = {r.day: float(r.value) for r in rows}
        span = (end - start).days + 1
        values = [found_days.get(start + timedelta(days=d)) for d in range(span)]
    else:  # previsão horária
        if location is None:
            raise DescribeError("informe o ponto (location) da previsão")
        f = weather_forecasts
        start_dt = datetime(start.year, start.month, start.day, tzinfo=LOCAL_TZ)
        end_dt = datetime(end.year, end.month, end.day, tzinfo=LOCAL_TZ) + timedelta(days=1)
        rows = await session.execute(
            select(f.c.valid_at, f.c.value).where(
                f.c.point_key == location,
                f.c.resolution == "hourly",
                f.c.variable == variable,
                f.c.valid_at >= start_dt,
                f.c.valid_at < end_dt,
            )
        )
        found_hours = {r.valid_at.astimezone(UTC): float(r.value) for r in rows}
        hours = int((end_dt - start_dt).total_seconds() // 3600)
        base = start_dt.astimezone(UTC)
        values = [found_hours.get(base + timedelta(hours=h)) for h in range(hours)]

    d: Description = describe(values)
    return DescribeResult(
        dataset=dataset_id,
        variable=variable,
        unit=var.unit,
        kind=ds.kind,
        location=location,
        start=start.isoformat(),
        end=end.isoformat(),
        expected=len(values),
        n=d.n,
        missing=d.missing,
        coverage=round(d.coverage, 4),
        mean=d.mean,
        median=d.median,
        minimum=d.minimum,
        maximum=d.maximum,
        std=d.std,
        p5=d.p5,
        p25=d.p25,
        p75=d.p75,
        p95=d.p95,
        outlier_count=d.outlier_count,
        outliers=list(d.outliers),
    )


# --- consultas auxiliares --------------------------------------------------------------------


def nearest_archive_point(
    lat: float, lon: float, points: Sequence[LocationInfo], max_km: float = MATCH_KM
) -> LocationInfo | None:
    best: tuple[float, LocationInfo] | None = None
    for p in points:
        if p.latitude is None or p.longitude is None:
            continue
        d = haversine_km(lat, lon, p.latitude, p.longitude)
        if d <= max_km and (best is None or d < best[0]):
            best = (d, p)
    return best[1] if best else None


async def daily_percentile_by_point(
    session: AsyncSession, month: int, q: float
) -> dict[str, tuple[float, int]]:
    """Percentil da chuva diária do mês em 1991–2020, por ponto: (valor, anos com dado)."""
    c = climate_daily
    year = cast(extract("year", c.c.day), Integer)
    rows = await session.execute(
        select(
            c.c.point_key,
            func.percentile_cont(q / 100).within_group(c.c.value),
            func.count(distinct(year)),
        )
        .where(
            c.c.variable == RAIN,
            cast(extract("month", c.c.day), Integer) == month,
            year >= NORMAL_START,
            year <= NORMAL_END,
        )
        .group_by(c.c.point_key)
    )
    return {r[0]: (float(r[1]), int(r[2])) for r in rows}


async def month_to_date_comparison(
    session: AsyncSession, point_key: str, until: date
) -> PeriodComparison | None:
    """Acumulado de 1 até `until` frente à média do mesmo intervalo em 1991–2020 (SQL)."""
    c = climate_daily
    day_of_month = cast(extract("day", c.c.day), Integer)
    year = cast(extract("year", c.c.day), Integer)
    base = select(func.sum(c.c.value), func.count()).where(
        c.c.point_key == point_key,
        c.c.variable == RAIN,
        cast(extract("month", c.c.day), Integer) == until.month,
        day_of_month <= until.day,
    )
    current = (await session.execute(base.where(year == until.year))).one()
    if int(current[1]) != until.day:
        return None
    history = await session.execute(
        select(year, func.sum(c.c.value), func.count())
        .where(
            c.c.point_key == point_key,
            c.c.variable == RAIN,
            cast(extract("month", c.c.day), Integer) == until.month,
            day_of_month <= until.day,
            year >= NORMAL_START,
            year <= NORMAL_END,
        )
        .group_by(year)
    )
    totals = [
        float(total)
        for y, total, count in history
        if int(count) == min(until.day, calendar.monthrange(int(y), until.month)[1])
    ]
    if len(totals) < 25:
        return None
    reference = sum(totals) / len(totals)
    current_total = float(current[0])
    return PeriodComparison(
        current=current_total,
        reference=reference,
        ratio=current_total / reference if reference > 0 else None,
        days=until.day,
        years_used=len(totals),
    )


async def _daily_rain(session: AsyncSession, point_key: str, condition: Any) -> dict[date, float]:
    c = climate_daily
    rows = await session.execute(
        select(c.c.day, c.c.value).where(
            c.c.point_key == point_key, c.c.variable == RAIN, condition
        )
    )
    return {r.day: float(r.value) for r in rows}


async def risk_high_counts(session: AsyncSession, now: datetime) -> tuple[int | None, int | None]:
    """Setores alto + crítico na última execução e na última até 24 h atrás."""

    async def count_for(run_filter: Any) -> int | None:
        run_id = (
            await session.execute(
                select(risk_runs.c.id)
                .where(risk_runs.c.status == "SUCCESS", run_filter)
                .order_by(risk_runs.c.computed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if run_id is None:
            return None
        a = risk_assessments
        total = (
            await session.execute(
                select(func.count()).where(
                    a.c.run_id == run_id, a.c.category.in_(("HIGH", "CRITICAL"))
                )
            )
        ).scalar_one()
        return int(total)

    now_count = await count_for(risk_runs.c.computed_at <= now)
    before = await count_for(risk_runs.c.computed_at <= now - timedelta(hours=24))
    return now_count, before


async def occurrences_by_subprefecture(
    session: AsyncSession, since: date, until: date
) -> dict[str, int]:
    o = flood_occurrences
    rows = await session.execute(
        select(o.c.subprefecture, func.count())
        .where(o.c.occurred_on >= since, o.c.occurred_on <= until, o.c.subprefecture.is_not(None))
        .group_by(o.c.subprefecture)
    )
    return {str(name): int(n) for name, n in rows}


# Ponto "central" da reanálise: até esta distância da Sé. Sem ele (carga inicial em
# andamento), os indicadores e regras do centro ficam indisponíveis em vez de usar outro ponto.
CENTER_MAX_KM = 10.0


def central_point(points: Sequence[LocationInfo]) -> LocationInfo | None:
    return nearest_archive_point(CITY_CENTER[0], CITY_CENTER[1], points, max_km=CENTER_MAX_KM)


# --- insights (FR-085) -----------------------------------------------------------------------


class MetricOut(BaseModel):
    name: str
    value: float | str | None
    unit: str
    kind: str
    source: str


class InsightOut(BaseModel):
    code: str
    severity: str
    text: str
    metrics: list[MetricOut]
    sources: list[str]
    rules_version: str


class InsightsResponse(BaseModel):
    generated_at: datetime
    rules_version: str
    items: list[InsightOut]
    notes: list[str]


def _out(insight: Insight) -> InsightOut:
    data = asdict(insight)
    return InsightOut.model_validate(
        {**data, "metrics": data["metrics"], "sources": list(insight.sources)}
    )


async def compute_insights(
    session: AsyncSession, now: datetime, credentials: dict[str, bool]
) -> InsightsResponse:
    today = local_today(now)
    yesterday = today - timedelta(days=1)
    insights: list[Insight] = []
    notes: list[str] = []
    archive = await archive_points(session)
    center = central_point(archive)
    if not archive:
        notes.append(
            "Reanálise ainda não carregada: IN-01, IN-02 e IN-03 aguardam a carga inicial."
        )
    elif center is None:
        notes.append("Ponto central da reanálise ainda em carga: IN-02 e IN-03 aguardam.")

    # IN-01 — chuva prevista nas próximas 24 h × p95 do mês no mesmo ponto.
    if archive:
        points: list[ForecastPoint] = await forecast_points(session)
        start = current_hour(now)
        hourly = await hourly_precipitation_by_point(session, start, start + timedelta(hours=24))
        rain = rain_inputs(hourly, start)
        p95 = await daily_percentile_by_point(session, today.month, 95.0)
        candidates: list[tuple[str, float, Insight]] = []
        for p in points:
            match = nearest_archive_point(p.latitude, p.longitude, archive)
            if match is None or p.point_key not in rain:
                continue
            value, years = p95.get(match.key, (0.0, 0))
            region = region_label(p.latitude, p.longitude)
            forecast_mm = rain[p.point_key].p24
            insight = in01_heavy_forecast(
                region=region,
                forecast_24h_mm=forecast_mm,
                p95_mm=value if years >= 25 else None,
                month=today.month,
            )
            if insight:
                candidates.append((region, forecast_mm, insight))
        # Um aviso por região, do maior para o menor volume previsto.
        seen: set[str] = set()
        for region, _mm, insight in sorted(candidates, key=lambda c: -c[1]):
            if region not in seen:
                seen.add(region)
                insights.append(insight)

    # IN-02 e IN-03 — no ponto central.
    if center is not None:
        comparison = await month_to_date_comparison(session, center.key, yesterday)
        if i2 := in02_month_to_date(
            region=center.label, comparison=comparison, month=yesterday.month
        ):
            insights.append(i2)
        recent = await _daily_rain(
            session, center.key, climate_daily.c.day >= yesterday - timedelta(days=120)
        )
        spell = current_dry_spell(recent, yesterday)
        month_days = await _daily_rain(
            session,
            center.key,
            cast(extract("month", climate_daily.c.day), Integer) == yesterday.month,
        )
        history = max_dry_spells_by_year(month_days, yesterday.month)
        if i3 := in03_dry_spell(
            region=center.label,
            current_days=spell,
            historical_max_spells=history,
            month=yesterday.month,
        ):
            insights.append(i3)

    # IN-04 — risco estimado.
    now_count, before = await risk_high_counts(session, now)
    if now_count is not None and (
        i4 := in04_risk_increase(now_count=now_count, before_count=before)
    ):
        insights.append(i4)

    # IN-05 — fontes.
    for source in await list_source_status(session, now=now, credentials=credentials):
        if i5 := in05_source_problem(
            source_name=source.name,
            freshness=source.freshness,
            reason=source.reason,
            last_success_at=source.last_success_at,
        ):
            insights.append(i5)

    # IN-06 — ocorrências.
    counts = await occurrences_by_subprefecture(session, today - timedelta(days=90), today)
    if i6 := in06_occurrence_concentration(counts_by_subprefecture=counts):
        insights.append(i6)

    insights.sort(key=lambda i: (0 if i.severity == "atencao" else 1, i.code))
    return InsightsResponse(
        generated_at=now,
        rules_version=INSIGHT_RULES_VERSION,
        items=[_out(i) for i in insights],
        notes=notes,
    )


# --- KPIs (FR-084) ---------------------------------------------------------------------------


class Kpi(BaseModel):
    code: str
    label: str
    value: float | None
    unit: str
    detail: str | None
    period_start: str | None
    period_end: str | None
    kind: str
    source: str
    freshness: str | None
    href: str
    available: bool


class KpisResponse(BaseModel):
    generated_at: datetime
    items: list[Kpi]


async def compute_kpis(
    session: AsyncSession, now: datetime, credentials: dict[str, bool]
) -> KpisResponse:
    today = local_today(now)
    yesterday = today - timedelta(days=1)
    status = await list_source_status(session, now=now, credentials=credentials)
    by_code = {s.code: s for s in status}
    items: list[Kpi] = []

    # Chuva prevista para as próximas 24 h.
    start = current_hour(now)
    points = await forecast_points(session)
    hourly = await hourly_precipitation_by_point(session, start, start + timedelta(hours=24))
    rain = rain_inputs(hourly, start)
    values = [(p, rain[p.point_key].p24) for p in points if p.point_key in rain]
    top = max(values, key=lambda item: item[1]) if values else None
    forecast_src = by_code.get(FORECAST_SOURCE)
    items.append(
        Kpi(
            code="forecast_rain_24h",
            label="Maior chuva prevista em 24 h",
            value=round(top[1], 1) if top else None,
            unit="mm",
            detail=(
                f"em {region_label(top[0].latitude, top[0].longitude)}; média dos "
                f"{len(values)} pontos: {fmt(sum(v for _, v in values) / len(values))} mm"
                if top
                else None
            ),
            period_start=start.isoformat(),
            period_end=(start + timedelta(hours=24)).isoformat(),
            kind="FORECAST",
            source="Open-Meteo (previsão)",
            freshness=forecast_src.freshness if forecast_src else None,
            href="/weather",
            available=top is not None,
        )
    )

    # Chuva do mês até ontem × média do mesmo intervalo (reanálise, ponto central).
    archive = await archive_points(session)
    center = central_point(archive)
    comparison = await month_to_date_comparison(session, center.key, yesterday) if center else None
    archive_src = by_code.get(ARCHIVE_SOURCE)
    items.append(
        Kpi(
            code="month_to_date_rain",
            label="Chuva do mês até ontem (Centro)",
            value=round(comparison.current, 1) if comparison else None,
            unit="mm",
            detail=(
                f"{fmt(comparison.ratio * 100, 0)}% da média dos mesmos {comparison.days} dias "
                "(1991–2020, reanálise)"
                if comparison and comparison.ratio is not None
                else "aguardando a carga da reanálise no ponto central"
            ),
            period_start=yesterday.replace(day=1).isoformat(),
            period_end=yesterday.isoformat(),
            kind="MODELED",
            source="Open-Meteo (reanálise ERA5/ERA5-Land)",
            freshness=archive_src.freshness if archive_src else None,
            href="/analytics?aba=chuva",
            available=comparison is not None,
        )
    )

    # Risco estimado.
    now_count, before = await risk_high_counts(session, now)
    engine = by_code.get("flood-risk-engine")
    items.append(
        Kpi(
            code="risk_high_sectors",
            label="Setores com risco estimado alto ou crítico",
            value=float(now_count) if now_count is not None else None,
            unit="setores",
            detail=f"há 24 h: {before}" if before is not None else "sem execução de 24 h atrás",
            period_start=None,
            period_end=now.isoformat(),
            kind="DERIVED",
            source="Motor de risco v0 (experimental)",
            freshness=engine.freshness if engine else None,
            href="/risk",
            available=now_count is not None,
        )
    )

    # Ocorrências nos últimos 30 dias.
    occ = sum(
        (await occurrences_by_subprefecture(session, today - timedelta(days=30), today)).values()
    )
    last_occ = (
        await session.execute(select(func.max(flood_occurrences.c.occurred_on)))
    ).scalar_one_or_none()
    occ_src = by_code.get("geosampa-flood-occurrences")
    items.append(
        Kpi(
            code="occurrences_30d",
            label="Ocorrências de alagamento/inundação em 30 dias",
            value=float(occ),
            unit="registros",
            detail=(
                f"registro mais recente na base: {last_occ:%d/%m/%Y}"
                if last_occ
                else "sem registros"
            ),
            period_start=(today - timedelta(days=30)).isoformat(),
            period_end=today.isoformat(),
            kind="OBSERVED",
            source="GeoSampa (Defesa Civil/SIGRC)",
            freshness=occ_src.freshness if occ_src else None,
            href="/map?modo=2d&camadas=ocorrencias,risco,regiao",
            available=last_occ is not None,
        )
    )

    # Fontes em dia.
    fresh = [s for s in status if s.freshness == "FRESH"]
    problems = [
        s.name for s in status if s.freshness != "FRESH" and s.reason != "missing_credentials"
    ]
    items.append(
        Kpi(
            code="sources_fresh",
            label="Fontes em dia",
            value=float(len(fresh)),
            unit=f"de {len(status)}",
            detail=("com problema: " + "; ".join(problems)) if problems else "nenhuma com problema",
            period_start=None,
            period_end=now.isoformat(),
            kind="DERIVED",
            source="estado das fontes",
            freshness=None,
            href="/status",
            available=bool(status),
        )
    )

    # Taxa de falhas das coletas em 7 dias.
    i = ingestion_runs
    total, failed = (
        await session.execute(
            select(func.count(), func.count().filter(i.c.status == "FAILED")).where(
                i.c.started_at >= now - timedelta(days=7)
            )
        )
    ).one()
    items.append(
        Kpi(
            code="ingestion_failure_rate_7d",
            label="Coletas com falha em 7 dias",
            value=round(100 * int(failed) / int(total), 1) if total else None,
            unit="%",
            detail=f"{failed} de {total} execuções",
            period_start=(now - timedelta(days=7)).isoformat(),
            period_end=now.isoformat(),
            kind="DERIVED",
            source="registro de coletas",
            freshness=None,
            href="/analytics?aba=fontes",
            available=bool(total),
        )
    )
    return KpisResponse(generated_at=now, items=items)

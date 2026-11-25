"""Central de relatórios (spec 010): validação, montadores, pedidos, geração e limpeza.

Os montadores usam os mesmos serviços da API (BR-150) e preenchem um `Report` neutro; os
escritores puros de `app/reports/` o transformam em PDF, CSV ou JSON.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.status import display_name
from app.analytics.places import region_label
from app.core.redaction import redact_text
from app.models.tables import report_files, report_requests, sector_terrain
from app.reports.content import (
    LOCAL_TZ,
    BarChart,
    Block,
    Column,
    Figures,
    Heading,
    Paragraph,
    Report,
    Table,
    format_number,
)
from app.reports.pdf import render_pdf
from app.reports.writers import render_csv, render_json
from app.services import alerts as alert_service
from app.services import risk as risk_service
from app.services import simulation as simulation_service
from app.services.analytics import archive_points, central_point
from app.services.analytics_series import SeriesError, get_series
from app.services.map_layers import forecast_point_features
from app.services.sources import list_source_status

ReportType = Literal["situacao", "risco", "alertas", "chuva", "simulacao"]
ReportFormat = Literal["pdf", "csv", "json"]
Status = Literal["QUEUED", "RUNNING", "DONE", "FAILED", "EXPIRED"]

MEDIA_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
}
RETENTION = timedelta(days=7)
MAX_BYTES = 20 * 1024 * 1024
HOURLY_LIMIT = 30
OPEN_LIMIT = 5
STUCK_RUNNING = timedelta(minutes=10)
STUCK_QUEUED = timedelta(minutes=30)
ALERT_PERIOD_MAX_DAYS = 90
RAIN_PERIOD_MAX_YEARS = 35
RAIN_DAILY_MAX_DAYS = 3 * 366
SIMULATION_BANNER = "SIMULAÇÃO — CENÁRIO HIPOTÉTICO, NÃO É PREVISÃO NEM ALERTA"

CATEGORY_LABELS = {
    "CRITICAL": "Crítico",
    "HIGH": "Alto",
    "MODERATE": "Moderado",
    "LOW": "Baixo",
    "UNKNOWN": "Desconhecido",
}
OFFICIAL_NOTE = (
    "Alertas oficiais: o texto é o da fonte. Esta plataforma não emite alertas oficiais; "
    "em emergência, ligue 199 (Defesa Civil) ou 193 (Bombeiros)."
)


class ReportParamsError(ValueError):
    """Parâmetro inválido: vira 422 com a mensagem."""


class ReportLimitError(RuntimeError):
    """Limite de pedidos: vira 429."""


# --- catálogo ----------------------------------------------------------------------------------


class ParamInfo(BaseModel):
    name: str
    label: str
    required: bool
    help: str


class ReportTypeInfo(BaseModel):
    code: ReportType
    title: str
    description: str
    formats: list[ReportFormat]
    params: list[ParamInfo]


REPORT_TYPES: dict[str, ReportTypeInfo] = {
    "situacao": ReportTypeInfo(
        code="situacao",
        title="Situação agora",
        description="Alertas oficiais, risco estimado, chuva prevista para 24 h e estado das "
        "fontes, no momento da geração.",
        formats=["pdf", "csv", "json"],
        params=[],
    ),
    "risco": ReportTypeInfo(
        code="risco",
        title="Risco por setor",
        description="Os setores de risco hidrológico com a categoria estimada, a chuva prevista, "
        "os fatores e o terreno.",
        formats=["pdf", "csv", "json"],
        params=[
            ParamInfo(
                name="subprefecture",
                label="Subprefeitura",
                required=False,
                help="Em branco: a cidade inteira.",
            )
        ],
    ),
    "alertas": ReportTypeInfo(
        code="alertas",
        title="Alertas do período",
        description="Alertas oficiais (Defesa Civil e INMET) com o texto da fonte, e alertas "
        "do sistema, num período de até 90 dias.",
        formats=["pdf", "csv", "json"],
        params=[
            ParamInfo(name="since", label="Desde", required=True, help="Data (AAAA-MM-DD)."),
            ParamInfo(name="until", label="Até", required=True, help="Data (AAAA-MM-DD)."),
            ParamInfo(name="category", label="Categoria", required=False, help="Em branco: todas."),
        ],
    ),
    "chuva": ReportTypeInfo(
        code="chuva",
        title="Chuva do período",
        description="Chuva da reanálise num ponto da grade, por dia, mês ou ano, com a normal "
        "1991–2020 nos totais mensais e anuais.",
        formats=["pdf", "csv", "json"],
        params=[
            ParamInfo(name="point", label="Ponto", required=False, help="Em branco: o centro."),
            ParamInfo(name="since", label="Desde", required=True, help="Data (AAAA-MM-DD)."),
            ParamInfo(name="until", label="Até", required=True, help="Data (AAAA-MM-DD)."),
            ParamInfo(name="grain", label="Agregação", required=True, help="day, month ou year."),
        ],
    ),
    "simulacao": ReportTypeInfo(
        code="simulacao",
        title="Simulação",
        description="Cenário, contagens, setores e comparação com a estimativa real de uma "
        "simulação do Laboratório.",
        formats=["pdf", "csv", "json"],
        params=[
            ParamInfo(
                name="simulation_id", label="Simulação", required=True, help="Id da simulação."
            )
        ],
    ),
}


# --- validação ---------------------------------------------------------------------------------


def _date(params: dict[str, Any], name: str, label: str) -> date:
    value = params.get(name)
    if not isinstance(value, str) or not value:
        raise ReportParamsError(f"Informe '{label}' (AAAA-MM-DD).")
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        raise ReportParamsError(f"'{label}' não é uma data válida (AAAA-MM-DD).") from None


def _local_day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=LOCAL_TZ).astimezone(UTC)


async def validate_params(
    session: AsyncSession, report_type: str, params: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Normaliza os parâmetros; erro com mensagem em português (AC-153)."""
    if report_type not in REPORT_TYPES:
        raise ReportParamsError("Tipo de relatório desconhecido.")
    today = now.astimezone(LOCAL_TZ).date()
    if report_type == "situacao":
        return {}
    if report_type == "risco":
        sub = params.get("subprefecture") or None
        if sub is not None:
            known = await risk_service.list_subprefectures(session)
            if sub not in known:
                raise ReportParamsError("Subprefeitura não encontrada entre os setores de risco.")
        return {"subprefecture": sub}
    if report_type == "alertas":
        since, until = _date(params, "since", "Desde"), _date(params, "until", "Até")
        if until < since:
            raise ReportParamsError("'Até' deve ser igual ou posterior a 'Desde'.")
        if (until - since).days + 1 > ALERT_PERIOD_MAX_DAYS:
            raise ReportParamsError(f"O período máximo é de {ALERT_PERIOD_MAX_DAYS} dias.")
        if since > today:
            raise ReportParamsError("O período começa no futuro.")
        category = params.get("category") or None
        if category not in (None, *alert_service.CATEGORY_LABELS):
            raise ReportParamsError("Categoria de alerta desconhecida.")
        return {"since": since.isoformat(), "until": until.isoformat(), "category": category}
    if report_type == "chuva":
        since, until = _date(params, "since", "Desde"), _date(params, "until", "Até")
        grain = params.get("grain") or "month"
        if grain not in ("day", "month", "year"):
            raise ReportParamsError("Agregação deve ser day, month ou year.")
        yesterday = today - timedelta(days=1)
        until = min(until, yesterday)
        if until < since:
            raise ReportParamsError("O período deve terminar depois do início (e até ontem).")
        if since < date(1991, 1, 1):
            raise ReportParamsError("A reanálise começa em 01/01/1991.")
        if (until - since).days > RAIN_PERIOD_MAX_YEARS * 366:
            raise ReportParamsError(f"O período máximo é de {RAIN_PERIOD_MAX_YEARS} anos.")
        if grain == "day" and (until - since).days > RAIN_DAILY_MAX_DAYS:
            raise ReportParamsError("Por dia, o período máximo é de 3 anos; use mês ou ano.")
        points = await archive_points(session)
        point = params.get("point") or None
        if point is None:
            center = central_point(points)
            if center is None:
                raise ReportParamsError("A reanálise ainda não foi carregada.")
            point = center.key
        elif point not in {p.key for p in points}:
            raise ReportParamsError("Ponto da reanálise desconhecido.")
        return {
            "point": point,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "grain": grain,
        }
    # simulacao
    raw = params.get("simulation_id")
    try:
        run_id = uuid.UUID(str(raw))
    except (ValueError, TypeError):
        raise ReportParamsError("Id de simulação inválido.") from None
    run = await simulation_service.get_run(session, run_id, now=now)
    if run is None:
        raise ReportParamsError("Simulação não encontrada (pode ter passado dos 30 dias).")
    return {"simulation_id": str(run_id)}


# --- montadores --------------------------------------------------------------------------------


def _label(category: str | None) -> str:
    return CATEGORY_LABELS.get(category or "UNKNOWN", category or "—")


def _subpref(name: str | None) -> str | None:
    return display_name(name) if name else None


SECTOR_COLUMNS = (
    Column("code", "Setor", width=0.9),
    Column("name", "Área", width=1.8),
    Column("subprefecture", "Subprefeitura", width=1.3),
    Column("grade", "Grau", "int", width=0.5),
    Column("category", "Risco estimado", width=0.9),
    Column("p1h_max_mm", "Chuva máx. 1 h", "number", unit="mm", width=0.8),
    Column("p24_mm", "Chuva 24 h", "number", unit="mm", width=0.8),
)


def _sector_row(area: Any) -> dict[str, Any]:
    return {
        "code": area.code,
        "name": area.name,
        "subprefecture": _subpref(area.subprefecture),
        "grade": area.grade,
        "category": _label(area.category),
        "category_code": area.category,
        "p1h_max_mm": area.p1h_max_mm,
        "p24_mm": area.p24_mm,
        "a72_mm": area.a72_mm,
        "in_flood_extent_100y": area.in_flood_extent_100y,
        "nearby_occurrences_12m": area.nearby_occurrences_12m,
        "factors": "; ".join(f.text for f in area.factors),
    }


def _official_table(key: str, title: str, alerts: list[Any], main: bool = False) -> Table:
    return Table(
        key=key,
        title=title,
        columns=(
            Column("category", "Categoria", width=1.1),
            Column("severity", "Severidade", width=0.9),
            Column("status", "Situação", width=0.95),
            Column("onset_at", "Início", "datetime", width=0.9),
            Column("expires_at", "Fim", "datetime", width=0.9),
            Column("headline", "Alerta (texto da fonte)", width=2.8),
            Column("area", "Subprefeituras atingidas", width=1.6),
        ),
        rows=tuple(
            {
                "category": a.category_label,
                "severity": a.level_name or a.severity_label,
                "status": STATUS_LABELS.get(a.status, a.status),
                "onset_at": a.onset_at,
                "expires_at": a.ended_at or a.expires_at,
                "headline": a.headline or a.event,
                "description": a.description,
                "instruction": a.instruction,
                "area": _area_text(a),
                "sender": a.sender_name,
                "source_url": a.web,
            }
            for a in alerts
        ),
        source="Defesa Civil (IDAP/MIDR) e INMET (Alert-AS)",
        data_kind="OFFICIAL_TEXT",
        note=OFFICIAL_NOTE,
        main=main,
        empty_text="Nenhum alerta oficial.",
    )


STATUS_LABELS = {
    "ACTIVE": "Vigente",
    "UPCOMING": "Próximo",
    "EXPIRED": "Encerrado",
    "CANCELLED": "Cancelado",
    "SUPERSEDED": "Substituído",
    "OPEN": "Aberto",
    "CLOSED": "Encerrado",
}


def _area_text(alert: Any) -> str:
    if alert.area_approximate:
        return "área aproximada"
    n = len(alert.subprefectures)
    if n >= 32:
        return "as 32 subprefeituras"
    return ", ".join(display_name(s) for s in alert.subprefectures) or "—"


def _system_table(alerts: list[Any]) -> Table:
    return Table(
        key="sistema",
        title="Alertas do sistema (estimativa e qualidade dos dados)",
        columns=(
            Column("category", "Categoria", width=1.4),
            Column("level", "Nível", width=0.6),
            Column("title", "Alerta", width=2.4),
            Column("opened_at", "Aberto em", "datetime", width=0.9),
            Column("closed_at", "Encerrado em", "datetime", width=0.9),
        ),
        rows=tuple(
            {
                "category": s.category_label,
                "level": {"CRITICAL": "Crítico", "HIGH": "Alto"}.get(s.level, "Aviso"),
                "title": s.title,
                "message": s.message,
                "opened_at": s.opened_at,
                "closed_at": s.closed_at,
                "rule": f"{s.rule_code} v{s.rules_version}",
            }
            for s in alerts
        ),
        source="Regras da plataforma (versão 1)",
        data_kind="DERIVED",
        note="Alertas do sistema não são alertas oficiais.",
        empty_text="Nenhum alerta do sistema.",
    )


def _risk_figures(counts: dict[str, int], run: Any) -> Figures:
    when = (
        run.computed_at.astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M")
        if run is not None
        else "sem cálculo"
    )
    return Figures(
        items=(
            ("Setores em crítico", str(counts.get("CRITICAL", 0))),
            ("Setores em alto", str(counts.get("HIGH", 0))),
            ("Setores em moderado", str(counts.get("MODERATE", 0))),
            ("Setores em baixo", str(counts.get("LOW", 0))),
            ("Sem estimativa", str(counts.get("UNKNOWN", 0))),
            ("Cálculo do risco", when),
        ),
        source=f"Motor de risco v0 ({run.engine_version if run else '—'}) · "
        "Setores: GeoSampa · Chuva: previsão Open-Meteo",
    )


RISK_ATTRIBUTIONS = (
    "Setores, manchas e ocorrências: GeoSampa — Prefeitura de São Paulo",
    "Previsão: Open-Meteo.com (CC BY 4.0)",
)
ALERT_ATTRIBUTIONS = (
    "Alertas: Defesa Civil (IDAP/MIDR) e INMET (Alert-AS)",
    "Subprefeituras: GeoSampa — Prefeitura de São Paulo",
)


async def _situacao(session: AsyncSession, now: datetime) -> Report:
    active = await alert_service.active_alerts(session, now)
    summary = await risk_service.risk_summary(session, now)
    high: list[Any] = []
    for category in ("CRITICAL", "HIGH"):
        items, _ = await risk_service.list_risk_areas(
            session, category=category, subprefecture=None, limit=500, offset=0
        )
        high.extend(items)
    points = await forecast_point_features(session, now)
    sources = await list_source_status(session, now=now, credentials={})
    blocks: list[Block] = [Heading("Alertas oficiais vigentes e próximos")]
    if not active.official and not active.sources_ok:
        blocks.append(
            Paragraph(
                "Uma fonte de alertas está atrasada ou indisponível: a ausência de alertas "
                "aqui não quer dizer que não haja alerta.",
                "warning",
            )
        )
    blocks.append(_official_table("alertas_oficiais", "Alertas oficiais", active.official, True))
    blocks += [
        _system_table(active.system),
        Heading("Risco de alagamento estimado (experimental)"),
        _risk_figures(summary.counts, summary.run),
        Table(
            key="setores_alto",
            title="Setores em risco alto ou crítico",
            columns=SECTOR_COLUMNS,
            rows=tuple(_sector_row(a) for a in high),
            source="GeoSampa × previsão Open-Meteo (motor de risco v0)",
            data_kind="DERIVED",
            note=risk_service.DISCLAIMER,
            empty_text="Nenhum setor em risco alto ou crítico na estimativa mais recente.",
        ),
        Heading("Chuva prevista para as próximas 24 h"),
        BarChart(
            title="Chuva prevista em 24 h por ponto da grade",
            labels=tuple(
                f"{region_label(f['geometry']['coordinates'][1], f['geometry']['coordinates'][0])}"
                f" ({f['properties']['point_key']})"
                for f in points
            ),
            values=tuple(float(f["properties"]["precipitation_24h"] or 0.0) for f in points),
            unit="mm",
            source="Open-Meteo.com (CC BY 4.0)",
            data_kind="FORECAST",
        ),
        Heading("Estado das fontes"),
        Table(
            key="fontes",
            title="Fontes de dados",
            columns=(
                Column("name", "Fonte", width=2.6),
                Column("freshness", "Frescor", width=0.9),
                Column("last_success_at", "Última coleta com sucesso", "datetime", width=1.2),
            ),
            rows=tuple(
                {
                    "code": s.code,
                    "name": s.name,
                    "freshness": FRESHNESS_LABELS.get(s.freshness, s.freshness),
                    "last_success_at": s.last_success_at,
                }
                for s in sources
            ),
            source="Registro de coletas da plataforma",
            data_kind="DERIVED",
        ),
    ]
    return Report(
        report_type="situacao",
        title="Situação agora — Município de São Paulo",
        generated_at=now,
        params={},
        blocks=tuple(blocks),
        warnings=(risk_service.DISCLAIMER, OFFICIAL_NOTE),
        attributions=(*ALERT_ATTRIBUTIONS, *RISK_ATTRIBUTIONS, "Observações: INMET"),
        versions={"risk_engine": summary.run.engine_version if summary.run else "—"},
    )


FRESHNESS_LABELS = {
    "FRESH": "Atualizado",
    "DELAYED": "Atrasado",
    "STALE": "Desatualizado",
    "UNAVAILABLE": "Indisponível",
    "UNKNOWN": "Sem coleta ainda",
}


async def _risco(session: AsyncSession, now: datetime, params: dict[str, Any]) -> Report:
    sub = params.get("subprefecture")
    summary = await risk_service.risk_summary(session, now)
    areas, total = await risk_service.list_risk_areas(
        session, category=None, subprefecture=sub, limit=5000, offset=0
    )
    terrain = {
        int(r.sector_id): r
        for r in (
            await session.execute(
                select(
                    sector_terrain.c.sector_id,
                    sector_terrain.c.elev_median_m,
                    sector_terrain.c.relative_elev_m,
                )
            )
        ).all()
    }
    rows = []
    for area in areas:
        row = _sector_row(area)
        t = terrain.get(area.id)
        row["elev_median_m"] = t.elev_median_m if t else None
        row["relative_elev_m"] = t.relative_elev_m if t else None
        rows.append(row)
    counts: dict[str, int] = {}
    for area in areas:
        counts[area.category] = counts.get(area.category, 0) + 1
    columns = (
        *SECTOR_COLUMNS,
        Column("relative_elev_m", "Elev. relativa", "number", unit="m", width=0.7),
        Column("factors", "Fatores", width=2.4),
    )
    scope = _subpref(sub) if sub else "Município de São Paulo"
    return Report(
        report_type="risco",
        title=f"Risco por setor — {scope}",
        subtitle=f"{total} setores de risco hidrológico da Prefeitura",
        generated_at=now,
        params=params,
        blocks=(
            _risk_figures(counts if sub else summary.counts, summary.run),
            Table(
                key="setores",
                title="Setores de risco e estimativa atual",
                columns=columns,
                rows=tuple(rows),
                source="GeoSampa × previsão Open-Meteo (motor de risco v0) · Terreno: Copernicus "
                "DEM GLO-30",
                data_kind="DERIVED",
                note="Elevação relativa: mediana do setor menos a do entorno de 1 km; negativa "
                "indica fundo de vale (modelo de superfície de 30 m). " + risk_service.DISCLAIMER,
                main=True,
            ),
        ),
        warnings=(risk_service.DISCLAIMER,),
        attributions=(
            *RISK_ATTRIBUTIONS,
            "Produced using Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and "
            "Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA",
        ),
        versions={"risk_engine": summary.run.engine_version if summary.run else "—"},
    )


async def _alertas(session: AsyncSession, now: datetime, params: dict[str, Any]) -> Report:
    since_day, until_day = date.fromisoformat(params["since"]), date.fromisoformat(params["until"])
    since = _local_day_start(since_day)
    until = _local_day_start(until_day + timedelta(days=1))
    category = params.get("category")
    official: list[Any] = []
    system: list[Any] = []
    if category in (None, "CIVIL_DEFENSE", "WEATHER_WARNING"):
        official = await alert_service.official_alerts_between(session, now, since, until, category)
    if category in (None, "RISK_ESTIMATE", "DATA_QUALITY"):
        system = await alert_service.system_alerts_between(session, since, until, category)
    by_category: dict[str, int] = {}
    for a in official:
        by_category[a.category_label] = by_category.get(a.category_label, 0) + 1
    period = f"{since_day:%d/%m/%Y} a {until_day:%d/%m/%Y}"
    blocks: list[Block] = [
        Figures(
            items=(
                (
                    "Alertas da Defesa Civil",
                    str(sum(a.category == "CIVIL_DEFENSE" for a in official)),
                ),
                ("Avisos do INMET", str(sum(a.category == "WEATHER_WARNING" for a in official))),
                ("Alertas do sistema", str(len(system))),
            )
        ),
        _official_table("alertas_oficiais", "Alertas oficiais", official, main=True),
    ]
    for a in official:
        text = " ".join(part for part in (a.description, a.instruction) if part)
        if text and text != a.headline:
            blocks.append(
                Paragraph(f"{a.category_label} — {a.headline or a.event}: {text}", "note")
            )
    blocks.append(_system_table(system))
    return Report(
        report_type="alertas",
        title="Alertas do período — Município de São Paulo",
        subtitle=f"De {period} (horário de Brasília)",
        generated_at=now,
        params=params,
        blocks=tuple(blocks),
        warnings=(OFFICIAL_NOTE,),
        attributions=ALERT_ATTRIBUTIONS,
    )


def _round(value: float | None, digits: int) -> float | None:
    """Sem ruído de ponto flutuante no JSON (112.00000000000001 -> 112.0)."""
    return round(value, digits) if value is not None else None


async def _chuva(session: AsyncSession, now: datetime, params: dict[str, Any]) -> Report:
    grain = params["grain"]
    try:
        series = await get_series(
            session,
            dataset="reanalysis-daily",
            variable="precipitation_sum",
            location=params["point"],
            start=date.fromisoformat(params["since"]),
            end=date.fromisoformat(params["until"]),
            grain=grain,
            agg="sum",
            compare="normal" if grain in ("month", "year") else None,
            now=now,
        )
    except SeriesError as exc:
        raise ReportParamsError(str(exc)) from None
    points = [p for p in series.points]
    values = [p.value for p in points if p.value is not None]
    point_info = next((p for p in await archive_points(session) if p.key == params["point"]), None)
    place = f"{point_info.label} ({point_info.key})" if point_info else params["point"]
    grain_word = {"day": "dia", "month": "mês", "year": "ano"}[grain]
    rows = tuple(
        {
            "start": date.fromisoformat(p.start[:10]),
            "value": _round(p.value, 2),
            "reference": _round(p.reference, 2),
            "anomaly_pct": _round((p.value / p.reference - 1) * 100, 1)
            if p.value is not None and p.reference
            else None,
            "coverage_pct": _round(p.coverage * 100, 1),
            "partial": p.partial or p.truncated,
        }
        for p in points
    )
    columns: tuple[Column, ...] = (
        Column("start", f"Início do {grain_word}", "date", width=1.0),
        Column("value", "Chuva", "number", unit="mm", width=0.9),
    )
    if series.reference_label:
        columns += (
            Column("reference", "Normal 1991–2020", "number", unit="mm", width=1.0),
            Column("anomaly_pct", "Diferença", "number", unit="%", digits=0, width=0.8),
        )
    columns += (
        Column("coverage_pct", "Dias com dado", "number", unit="%", digits=0, width=0.8),
        Column("partial", "Parcial", width=0.6),
    )
    blocks: list[Block] = [
        Figures(
            items=(
                ("Total no período", f"{format_number(sum(values), 1)} mm" if values else "—"),
                (f"Maior {grain_word}", f"{format_number(max(values), 1)} mm" if values else "—"),
                (
                    f"Média por {grain_word}",
                    f"{format_number(sum(values) / len(values), 1)} mm" if values else "—",
                ),
            ),
            source=f"{series.dataset_name} · {place}",
        )
    ]
    if 0 < len(points) <= 36:
        blocks.append(
            BarChart(
                title=f"Chuva por {grain_word}",
                labels=tuple(
                    date.fromisoformat(p.start[:10]).strftime(
                        "%d/%m/%Y" if grain == "day" else "%m/%Y" if grain == "month" else "%Y"
                    )
                    for p in points
                ),
                values=tuple(p.value or 0.0 for p in points),
                unit="mm",
                source=series.attribution or "Open-Meteo.com (CC BY 4.0)",
                data_kind="MODELED",
            )
        )
    blocks.append(
        Table(
            key="serie",
            title=f"Chuva por {grain_word} — {place}",
            columns=columns,
            rows=rows,
            source=series.attribution or "Open-Meteo.com (CC BY 4.0)",
            data_kind="MODELED",
            note=" ".join(series.caveats),
            main=True,
        )
    )
    return Report(
        report_type="chuva",
        title=f"Chuva do período — {place}",
        subtitle=f"De {date.fromisoformat(params['since']):%d/%m/%Y} a "
        f"{date.fromisoformat(params['until']):%d/%m/%Y}, por {grain_word}",
        generated_at=now,
        params=params,
        blocks=tuple(blocks),
        warnings=("Reanálise é estimativa de modelo, não medição.", *series.caveats[1:2]),
        attributions=("Reanálise: Open-Meteo.com (ERA5/ERA5-Land, CC BY 4.0)",),
    )


async def _simulacao(session: AsyncSession, now: datetime, params: dict[str, Any]) -> Report:
    run_id = uuid.UUID(params["simulation_id"])
    run = await simulation_service.get_run(session, run_id, now=now)
    if run is None:
        raise ReportParamsError("Simulação não encontrada (pode ter passado dos 30 dias).")
    sectors, _ = await simulation_service.list_sectors(
        session, run_id, category=None, subprefecture=None, limit=5000, offset=0
    )
    rows = tuple(
        {
            "code": s.code,
            "name": s.name,
            "subprefecture": _subpref(s.subprefecture),
            "grade": s.grade,
            "category": _label(s.category),
            "real_category": _label(s.real_category) if s.real_category else None,
            "p1h_max_mm": s.p1h_max_mm,
            "p24_mm": s.p24_mm,
            "p_high_pct": s.p_high * 100 if s.p_high is not None else None,
            "factors": "; ".join(f.text for f in s.factors),
        }
        for s in sectors
    )
    columns: tuple[Column, ...] = (
        Column("code", "Setor", width=0.9),
        Column("name", "Área", width=1.7),
        Column("subprefecture", "Subprefeitura", width=1.2),
        Column("category", "Simulado", width=0.8),
        Column("real_category", "Estimativa real", width=0.9),
        Column("p1h_max_mm", "Chuva máx. 1 h", "number", unit="mm", width=0.8),
        Column("p24_mm", "Chuva 24 h", "number", unit="mm", width=0.8),
    )
    if run.members > 1:
        columns += (Column("p_high_pct", "Chance de alto ou mais", "number", unit="%", digits=0),)
    comparison = run.comparison
    banner = SIMULATION_BANNER if run.mode == "SIMULATION" else run.banner.upper()
    return Report(
        report_type="simulacao",
        title="Simulação — " + run.scenario_text,
        subtitle=f"Executada em {run.created_at.astimezone(LOCAL_TZ):%d/%m/%Y %H:%M} · "
        f"modo {run.mode} · motor de simulação {run.simulation_engine_version}",
        generated_at=now,
        params=params,
        mode="SIMULATION",
        banner=banner,
        blocks=(
            Figures(
                items=(
                    ("Crítico (simulado)", str(run.counts.get("CRITICAL", 0))),
                    ("Alto (simulado)", str(run.counts.get("HIGH", 0))),
                    ("Moderado (simulado)", str(run.counts.get("MODERATE", 0))),
                    ("Sobem em relação ao real", str(comparison.raised)),
                    ("Descem em relação ao real", str(comparison.lowered)),
                    ("Setores", str(run.sector_count)),
                ),
                source=f"Motor de risco {run.risk_engine_version} sobre os setores do GeoSampa",
            ),
            Table(
                key="subprefeituras",
                title="Comparação por subprefeitura",
                columns=(
                    Column("name", "Subprefeitura", width=1.6),
                    Column("sectors", "Setores", "int", width=0.6),
                    Column("sim", "Alto ou mais (simulado)", "int", width=0.9),
                    Column("real", "Alto ou mais (real)", "int", width=0.9),
                    Column("raised", "Sobem", "int", width=0.6),
                ),
                rows=tuple(
                    {
                        "name": _subpref(s.name),
                        "sectors": s.sectors,
                        "sim": s.high_or_above_simulated,
                        "real": s.high_or_above_real,
                        "raised": s.raised,
                    }
                    for s in comparison.subprefectures
                ),
                source="Simulação × estimativa real mais recente",
                data_kind="SIMULATED",
            ),
            Table(
                key="setores",
                title="Setores na simulação",
                columns=columns,
                rows=rows,
                source="Laboratório de simulação (motor de risco v0)",
                data_kind="SIMULATED",
                note=run.disclaimer,
                main=True,
            ),
        ),
        warnings=(run.disclaimer,),
        attributions=RISK_ATTRIBUTIONS,
        versions={
            "simulation_engine": run.simulation_engine_version,
            "risk_engine": run.risk_engine_version,
        },
    )


async def build_report(
    session: AsyncSession, report_type: str, params: dict[str, Any], now: datetime
) -> Report:
    if report_type == "situacao":
        return await _situacao(session, now)
    if report_type == "risco":
        return await _risco(session, now, params)
    if report_type == "alertas":
        return await _alertas(session, now, params)
    if report_type == "chuva":
        return await _chuva(session, now, params)
    if report_type == "simulacao":
        return await _simulacao(session, now, params)
    raise ReportParamsError("Tipo de relatório desconhecido.")


def render(report: Report, fmt: str) -> bytes:
    if fmt == "pdf":
        return render_pdf(report)
    if fmt == "csv":
        return render_csv(report)
    return render_json(report)


# --- pedidos ----------------------------------------------------------------------------------


class ReportRequest(BaseModel):
    id: uuid.UUID
    report_type: str
    format: str
    title: str
    params: dict[str, Any]
    mode: str
    status: Status
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None
    bytes: int | None
    filename: str | None
    download_url: str | None


def _filename(report_type: str, fmt: str, now: datetime) -> str:
    return f"{report_type}_{now.astimezone(LOCAL_TZ):%Y-%m-%d_%H%M}.{fmt}"


def _out(row: Any, now: datetime) -> ReportRequest:
    status = row.status
    if status == "DONE" and row.expires_at is not None and row.expires_at <= now:
        status = "EXPIRED"
    return ReportRequest(
        id=row.id,
        report_type=row.report_type,
        format=row.format,
        title=row.title,
        params=row.params or {},
        mode=row.mode,
        status=status,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        expires_at=row.expires_at,
        bytes=row.bytes,
        filename=row.filename,
        download_url=f"/api/v1/reports/{row.id}/download" if status == "DONE" else None,
    )


async def create_request(
    session: AsyncSession, report_type: str, fmt: str, params: dict[str, Any], now: datetime
) -> ReportRequest:
    if fmt not in MEDIA_TYPES:
        raise ReportParamsError("Formato deve ser pdf, csv ou json.")
    clean = await validate_params(session, report_type, params, now)
    recent, open_now = (
        await session.execute(
            select(
                func.count().filter(report_requests.c.created_at > now - timedelta(hours=1)),
                func.count().filter(report_requests.c.status.in_(("QUEUED", "RUNNING"))),
            )
        )
    ).one()
    if int(recent) >= HOURLY_LIMIT:
        raise ReportLimitError(
            f"Limite de {HOURLY_LIMIT} relatórios por hora atingido. Tente de novo mais tarde."
        )
    if int(open_now) >= OPEN_LIMIT:
        raise ReportLimitError(f"Já há {OPEN_LIMIT} relatórios em geração. Aguarde algum terminar.")
    info = REPORT_TYPES[report_type]
    row = (
        await session.execute(
            report_requests.insert()
            .values(
                id=uuid.uuid4(),
                report_type=report_type,
                format=fmt,
                params=clean,
                title=info.title,
                mode="SIMULATION" if report_type == "simulacao" else "REAL",
                status="QUEUED",
                created_at=now,
            )
            .returning(report_requests)
        )
    ).one()
    await session.commit()
    return _out(row, now)


async def get_request(
    session: AsyncSession, request_id: uuid.UUID, now: datetime
) -> ReportRequest | None:
    row = (
        await session.execute(select(report_requests).where(report_requests.c.id == request_id))
    ).one_or_none()
    return _out(row, now) if row is not None else None


async def list_requests(
    session: AsyncSession, ids: list[uuid.UUID], now: datetime
) -> list[ReportRequest]:
    if not ids:
        return []
    rows = (
        await session.execute(
            select(report_requests)
            .where(report_requests.c.id.in_(ids))
            .order_by(report_requests.c.created_at.desc())
        )
    ).all()
    return [_out(r, now) for r in rows]


@dataclass(frozen=True)
class ReportFile:
    content: bytes
    filename: str
    media_type: str


async def get_file(session: AsyncSession, request_id: uuid.UUID) -> ReportFile | None:
    row = (
        await session.execute(
            select(report_files.c.content, report_requests.c.filename, report_requests.c.media_type)
            .join(report_requests, report_requests.c.id == report_files.c.request_id)
            .where(report_files.c.request_id == request_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return ReportFile(bytes(row.content), row.filename, row.media_type)


async def generate(
    session: AsyncSession,
    request_id: uuid.UUID,
    now: datetime,
    clock: Callable[[], datetime] | None = None,
) -> str:
    """Gera o arquivo de um pedido em fila (FR-151). Devolve o estado final.

    `now` é o horário de referência do conteúdo; `clock` dá o horário real do fim (o worker
    passa o relógio; os testes usam um horário fixo).
    """
    claimed = (
        await session.execute(
            update(report_requests)
            .where(report_requests.c.id == request_id, report_requests.c.status == "QUEUED")
            .values(status="RUNNING", started_at=now)
            .returning(report_requests)
        )
    ).one_or_none()
    await session.commit()
    if claimed is None:
        return "SKIPPED"
    try:
        report = await build_report(session, claimed.report_type, claimed.params or {}, now)
        content = render(report, claimed.format)
        if len(content) > MAX_BYTES:
            raise ValueError("relatório acima de 20 MB; reduza o período ou o filtro")
    except Exception as exc:
        await session.rollback()
        message = (
            str(exc)
            if isinstance(exc, ReportParamsError | ValueError)
            else f"erro inesperado ({type(exc).__name__})"
        )
        await session.execute(
            update(report_requests)
            .where(report_requests.c.id == request_id)
            .values(status="FAILED", error=redact_text(message)[:500], finished_at=now)
        )
        await session.commit()
        return "FAILED"
    finished = clock() if clock is not None else now
    await session.execute(report_files.insert().values(request_id=request_id, content=content))
    await session.execute(
        update(report_requests)
        .where(report_requests.c.id == request_id)
        .values(
            status="DONE",
            title=report.title,
            finished_at=finished,
            expires_at=finished + RETENTION,
            bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            filename=_filename(claimed.report_type, claimed.format, now),
            media_type=MEDIA_TYPES[claimed.format],
        )
    )
    await session.commit()
    return "DONE"


async def housekeeping(session: AsyncSession, now: datetime) -> tuple[int, int]:
    """Apaga arquivos vencidos (FR-155) e marca como falhos os pedidos presos (FR-151)."""
    expired = (
        await session.execute(
            delete(report_files)
            .where(
                report_files.c.request_id.in_(
                    select(report_requests.c.id).where(report_requests.c.expires_at <= now)
                )
            )
            .returning(report_files.c.request_id)
        )
    ).all()
    await session.execute(
        update(report_requests)
        .where(report_requests.c.status == "DONE", report_requests.c.expires_at <= now)
        .values(status="EXPIRED")
    )
    stuck = (
        await session.execute(
            update(report_requests)
            .where(
                (
                    (report_requests.c.status == "RUNNING")
                    & (report_requests.c.started_at < now - STUCK_RUNNING)
                )
                | (
                    (report_requests.c.status == "QUEUED")
                    & (report_requests.c.created_at < now - STUCK_QUEUED)
                )
            )
            .values(
                status="FAILED",
                error="A geração não terminou a tempo. Peça o relatório de novo.",
                finished_at=now,
            )
            .returning(report_requests.c.id)
        )
    ).all()
    await session.commit()
    return len(expired), len(stuck)

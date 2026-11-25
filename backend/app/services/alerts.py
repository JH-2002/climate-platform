"""Alertas (spec 009): avaliação das regras do sistema e consultas da API.

Alertas oficiais (IDAP, INMET) e alertas do sistema ficam em tabelas separadas e saem sempre
com a categoria e o rótulo (BR-140). O texto oficial é devolvido como a fonte escreveu (BR-141).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.rules import (
    DEFAULT_THRESHOLDS,
    RULES_VERSION,
    WATCHED_SOURCES,
    Action,
    OpenAlert,
    Snapshot,
    SourceState,
    SubprefectureRisk,
    Thresholds,
    evaluate,
    plan_actions,
)
from app.alerts.status import (
    SEVERITY_RANK,
    OfficialStatus,
    official_status,
    severity_label,
)
from app.core.config import Settings
from app.integrations.inmet.warnings import INMET_LEVELS
from app.models.tables import (
    data_sources,
    hydro_risk_sectors,
    official_alerts,
    risk_assessments,
    system_alerts,
)
from app.services.freshness import Freshness, classify_freshness
from app.services.risk import latest_run

OfficialCategory = Literal["CIVIL_DEFENSE", "WEATHER_WARNING"]
SystemCategory = Literal["RISK_ESTIMATE", "DATA_QUALITY"]
AnyCategory = Literal["CIVIL_DEFENSE", "WEATHER_WARNING", "RISK_ESTIMATE", "DATA_QUALITY"]

CATEGORY_LABELS: dict[str, str] = {
    "CIVIL_DEFENSE": "Alerta oficial — Defesa Civil",
    "WEATHER_WARNING": "Aviso meteorológico oficial — INMET",
    "RISK_ESTIMATE": "Estimativa do sistema — não é alerta oficial",
    "DATA_QUALITY": "Qualidade dos dados",
}
SOURCE_BY_CATEGORY = {"CIVIL_DEFENSE": "idap-alerts", "WEATHER_WARNING": "inmet-warnings"}
ALERT_SOURCES = ("idap-alerts", "inmet-warnings")
UPCOMING_WINDOW = timedelta(hours=48)
HISTORY_MAX_DAYS = 90
PAGE_SIZE = 50
CGE_URL = "https://www.cgesp.org"
OFFICIAL_CHANNEL = (
    "Para receber os alertas oficiais da Defesa Civil no celular, envie um SMS com o seu CEP "
    "para 40199. Em emergência, ligue 199 (Defesa Civil) ou 193 (Bombeiros)."
)
EVALUATION_LOCK = 9009


# --- modelos da API -----------------------------------------------------------------------------


class OfficialAlert(BaseModel):
    id: int
    category: OfficialCategory
    category_label: str
    source_code: str
    attribution: str
    sender_name: str | None
    msg_type: str
    event: str | None
    severity: str | None
    severity_label: str
    level_name: str | None
    color: str | None
    urgency: str | None
    certainty: str | None
    headline: str | None
    description: str | None
    instruction: str | None
    web: str | None
    area_desc: str | None
    sent_at: datetime
    onset_at: datetime | None
    expires_at: datetime | None
    ended_at: datetime | None
    status: OfficialStatus
    subprefectures: list[str]
    city_fraction: float | None
    area_approximate: bool


class OfficialAlertDetail(OfficialAlert):
    geometry: dict[str, Any] | None
    references: list[str]


class SystemAlert(BaseModel):
    id: int
    rule_code: str
    rules_version: str
    category: SystemCategory
    category_label: str
    level: str
    scope_label: str
    title: str
    message: str
    details: dict[str, Any]
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    status: Literal["OPEN", "CLOSED"]


class AlertSource(BaseModel):
    code: str
    name: str
    attribution: str
    freshness: Freshness
    last_success_at: datetime | None


class ActiveAlerts(BaseModel):
    generated_at: datetime
    official: list[OfficialAlert]
    system: list[SystemAlert]
    counts: dict[str, int]
    sources: list[AlertSource]
    sources_ok: bool
    cge_url: str = CGE_URL
    official_channel: str = OFFICIAL_CHANNEL


class HistoryEntry(BaseModel):
    kind: Literal["official", "system"]
    id: int
    category: AnyCategory
    category_label: str
    title: str
    level: str | None
    level_label: str
    start_at: datetime | None
    end_at: datetime | None
    status: str


class AlertHistory(BaseModel):
    items: list[HistoryEntry]
    total: int
    page: int
    page_size: int
    since: datetime
    until: datetime


class RuleInfo(BaseModel):
    code: str
    category: SystemCategory
    description: str
    threshold: str
    open_alerts: int


class RulesInfo(BaseModel):
    version: str
    clear_after: int
    rules: list[RuleInfo]
    note: str


def thresholds_from(settings: Settings) -> Thresholds:
    return Thresholds(
        risk_stale_hours=settings.alert_risk_stale_hours, clear_after=settings.alert_clear_after
    )


# --- avaliação das regras ---------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationSummary:
    opened: int
    updated: int
    closed: int
    open_total: int


async def _source_states(session: AsyncSession, codes: Sequence[str], now: datetime) -> list[Any]:
    rows = (
        await session.execute(select(data_sources).where(data_sources.c.code.in_(list(codes))))
    ).all()
    return [
        (
            row,
            classify_freshness(
                now=now,
                last_success_at=row.last_success_at,
                expected_interval_s=row.expected_interval_s,
                last_run_status=row.last_status,
                enabled=row.enabled,
            ).freshness,
        )
        for row in rows
    ]


async def build_snapshot(session: AsyncSession, now: datetime) -> Snapshot:
    """Retrato do estado real (nunca de simulação, BR-143)."""
    run = await latest_run(session)
    subs: list[SubprefectureRisk] = []
    if run is not None:
        rows = await session.execute(
            select(
                hydro_risk_sectors.c.subprefecture,
                func.count().filter(risk_assessments.c.category == "HIGH"),
                func.count().filter(risk_assessments.c.category == "CRITICAL"),
            )
            .join(hydro_risk_sectors, hydro_risk_sectors.c.id == risk_assessments.c.sector_id)
            .where(
                risk_assessments.c.run_id == run.id,
                risk_assessments.c.category.in_(("HIGH", "CRITICAL")),
            )
            .group_by(hydro_risk_sectors.c.subprefecture)
        )
        subs = [
            SubprefectureRisk(name or "SEM SUBPREFEITURA", int(high), int(critical))
            for name, high, critical in rows.tuples()
        ]
    sources = [
        SourceState(row.code, freshness, row.last_success_at)
        for row, freshness in await _source_states(session, list(WATCHED_SOURCES), now)
    ]
    return Snapshot(
        now=now,
        risk_computed_at=run.computed_at if run is not None else None,
        subprefectures=sorted(subs, key=lambda s: s.name),
        sources=sorted(sources, key=lambda s: s.code),
    )


async def _apply(session: AsyncSession, action: Action, now: datetime) -> None:
    c = action.condition
    if action.kind == "open" and c is not None:
        await session.execute(
            insert(system_alerts)
            .values(
                rule_code=c.rule_code,
                rules_version=RULES_VERSION,
                scope_key=c.scope_key,
                scope_label=c.scope_label,
                category=c.category,
                level=c.level,
                title=c.title,
                message=c.message,
                details=c.details,
                opened_at=now,
                updated_at=now,
                clear_count=0,
            )
            .on_conflict_do_nothing(
                index_elements=["rule_code", "scope_key"],
                index_where=system_alerts.c.closed_at.is_(None),
            )
        )
    elif action.kind == "update" and c is not None:
        await session.execute(
            system_alerts.update()
            .where(system_alerts.c.id == action.alert_id)
            .values(
                level=c.level,
                title=c.title,
                message=c.message,
                details=c.details,
                scope_label=c.scope_label,
                rules_version=RULES_VERSION,
                updated_at=now,
                clear_count=0,
            )
        )
    elif action.kind == "miss":
        await session.execute(
            system_alerts.update()
            .where(system_alerts.c.id == action.alert_id)
            .values(clear_count=action.clear_count)
        )
    elif action.kind == "close":
        await session.execute(
            system_alerts.update()
            .where(system_alerts.c.id == action.alert_id)
            .values(closed_at=now, updated_at=now, clear_count=action.clear_count)
        )


async def evaluate_system_alerts(
    session: AsyncSession, now: datetime, thresholds: Thresholds = DEFAULT_THRESHOLDS
) -> EvaluationSummary:
    """Avalia as regras e aplica as ações numa transação (FR-144, AC-143)."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": EVALUATION_LOCK})
    snapshot = await build_snapshot(session, now)
    rows = (
        await session.execute(select(system_alerts).where(system_alerts.c.closed_at.is_(None)))
    ).all()
    open_alerts = [
        OpenAlert(r.id, r.rule_code, r.scope_key, r.level, r.message, r.clear_count) for r in rows
    ]
    actions = plan_actions(evaluate(snapshot, thresholds), open_alerts, thresholds)
    for action in actions:
        await _apply(session, action, now)
    open_total = (
        await session.execute(
            select(func.count())
            .select_from(system_alerts)
            .where(system_alerts.c.closed_at.is_(None))
        )
    ).scalar_one()
    await session.commit()
    return EvaluationSummary(
        opened=sum(a.kind == "open" for a in actions),
        updated=sum(a.kind == "update" for a in actions),
        closed=sum(a.kind == "close" for a in actions),
        open_total=int(open_total),
    )


# --- consultas --------------------------------------------------------------------------------


def _official_columns() -> list[Any]:
    a = official_alerts
    return [
        a.c.id,
        a.c.category,
        data_sources.c.code.label("source_code"),
        data_sources.c.attribution,
        a.c.sender_name,
        a.c.msg_type,
        a.c.event,
        a.c.severity,
        a.c.color,
        a.c.urgency,
        a.c.certainty,
        a.c.headline,
        a.c.description,
        a.c.instruction,
        a.c.web,
        a.c.area_desc,
        a.c.sent_at,
        a.c.onset_at,
        a.c.expires_at,
        a.c.ended_at,
        a.c.ended_reason,
        a.c.subprefectures,
        a.c.city_fraction,
        a.c.area_approximate,
    ]


def _official_select(*extra: Any) -> Select[Any]:
    return (
        select(*_official_columns(), *extra)
        .join(data_sources, data_sources.c.id == official_alerts.c.source_id)
        .where(official_alerts.c.msg_type != "Cancel")
    )


def _not_over(now: datetime) -> Any:
    """Vigente ou próximo (até 48 h): não encerrado pela fonte e ainda não passou do fim."""
    a = official_alerts.c
    return and_(
        a.ended_at.is_(None),
        a.expires_at > now,
        a.onset_at <= now + UPCOMING_WINDOW,
    )


def _official(row: Any, now: datetime) -> OfficialAlert:
    level = INMET_LEVELS.get(row.severity or "") if row.category == "WEATHER_WARNING" else None
    return OfficialAlert(
        id=row.id,
        category=row.category,
        category_label=CATEGORY_LABELS[row.category],
        source_code=row.source_code,
        attribution=row.attribution,
        sender_name=row.sender_name,
        msg_type=row.msg_type,
        event=row.event,
        severity=row.severity,
        severity_label=severity_label(row.severity),
        level_name=f"{level[1].capitalize()} — {level[0]}" if level else None,
        color=row.color,
        urgency=row.urgency,
        certainty=row.certainty,
        headline=row.headline,
        description=row.description,
        instruction=row.instruction,
        web=row.web,
        area_desc=row.area_desc,
        sent_at=row.sent_at,
        onset_at=row.onset_at,
        expires_at=row.expires_at,
        ended_at=row.ended_at,
        status=official_status(now, row.onset_at, row.expires_at, row.ended_reason),
        subprefectures=list(row.subprefectures or []),
        city_fraction=row.city_fraction,
        area_approximate=row.area_approximate,
    )


def _system(row: Any) -> SystemAlert:
    return SystemAlert(
        id=row.id,
        rule_code=row.rule_code,
        rules_version=row.rules_version,
        category=row.category,
        category_label=CATEGORY_LABELS[row.category],
        level=row.level,
        scope_label=row.scope_label,
        title=row.title,
        message=row.message,
        details=row.details or {},
        opened_at=row.opened_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
        status="OPEN" if row.closed_at is None else "CLOSED",
    )


def _official_order(alert: OfficialAlert) -> tuple[int, int, float]:
    """Defesa Civil primeiro; depois vigentes antes de próximos; depois a severidade."""
    category = 0 if alert.category == "CIVIL_DEFENSE" else 1
    status = 0 if alert.status == "ACTIVE" else 1
    onset = alert.onset_at.timestamp() if alert.onset_at else 0.0
    return (category * 10 + status, -SEVERITY_RANK.get(alert.severity or "", 0), onset)


_LEVEL_RANK = {"CRITICAL": 3, "HIGH": 2, "WARNING": 1}


async def alert_sources(session: AsyncSession, now: datetime) -> list[AlertSource]:
    states = await _source_states(session, ALERT_SOURCES, now)
    return [
        AlertSource(
            code=row.code,
            name=row.name,
            attribution=row.attribution,
            freshness=freshness,
            last_success_at=row.last_success_at,
        )
        for row, freshness in sorted(states, key=lambda s: ALERT_SOURCES.index(s[0].code))
    ]


async def active_alerts(session: AsyncSession, now: datetime) -> ActiveAlerts:
    rows = (await session.execute(_official_select().where(_not_over(now)))).all()
    official = sorted((_official(r, now) for r in rows), key=_official_order)
    system_rows = (
        await session.execute(select(system_alerts).where(system_alerts.c.closed_at.is_(None)))
    ).all()
    system = sorted(
        (_system(r) for r in system_rows),
        key=lambda s: (s.category != "RISK_ESTIMATE", -_LEVEL_RANK.get(s.level, 0), s.scope_label),
    )
    sources = await alert_sources(session, now)
    counts = {
        "official_active": sum(a.status == "ACTIVE" for a in official),
        "official_upcoming": sum(a.status == "UPCOMING" for a in official),
        "civil_defense_active": sum(
            a.status == "ACTIVE" and a.category == "CIVIL_DEFENSE" for a in official
        ),
        "weather_warning_active": sum(
            a.status == "ACTIVE" and a.category == "WEATHER_WARNING" for a in official
        ),
        "risk_estimate": sum(s.category == "RISK_ESTIMATE" for s in system),
        "data_quality": sum(s.category == "DATA_QUALITY" for s in system),
    }
    return ActiveAlerts(
        generated_at=now,
        official=official,
        system=system,
        counts=counts,
        sources=sources,
        sources_ok=bool(sources) and all(s.freshness in ("FRESH", "DELAYED") for s in sources),
    )


async def official_alert_detail(
    session: AsyncSession, alert_id: int, now: datetime
) -> OfficialAlertDetail | None:
    row = (
        await session.execute(
            _official_select(
                func.ST_AsGeoJSON(
                    func.ST_SimplifyPreserveTopology(official_alerts.c.geom, 0.0005), 5
                ).label("geojson"),
                official_alerts.c.refs,
            ).where(official_alerts.c.id == alert_id)
        )
    ).one_or_none()
    if row is None:
        return None
    base = _official(row, now)
    return OfficialAlertDetail(
        **base.model_dump(),
        geometry=json.loads(row.geojson) if row.geojson else None,
        references=list(row.refs or []),
    )


async def alerts_at(
    session: AsyncSession, lat: float, lon: float, now: datetime
) -> list[OfficialAlert]:
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    rows = (
        await session.execute(
            _official_select().where(_not_over(now), func.ST_Covers(official_alerts.c.geom, point))
        )
    ).all()
    return sorted((_official(r, now) for r in rows), key=_official_order)


def _history_window(
    now: datetime, since: datetime | None, until: datetime | None
) -> tuple[datetime, datetime]:
    end = until or now
    start = since or end - timedelta(days=7)
    if start >= end:
        raise ValueError("'desde' deve ser anterior a 'ate'.")
    if end - start > timedelta(days=HISTORY_MAX_DAYS):
        raise ValueError(f"O período máximo é de {HISTORY_MAX_DAYS} dias.")
    return start, end


async def alert_history(
    session: AsyncSession,
    now: datetime,
    *,
    category: AnyCategory | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = 1,
) -> AlertHistory:
    start, end = _history_window(now, since, until)
    entries: list[HistoryEntry] = []
    if category in (None, "CIVIL_DEFENSE", "WEATHER_WARNING"):
        query = _official_select().where(
            official_alerts.c.sent_at < end,
            or_(official_alerts.c.expires_at.is_(None), official_alerts.c.expires_at >= start),
        )
        if category is not None:
            query = query.where(official_alerts.c.category == category)
        for row in (await session.execute(query)).all():
            alert = _official(row, now)
            entries.append(
                HistoryEntry(
                    kind="official",
                    id=alert.id,
                    category=alert.category,
                    category_label=alert.category_label,
                    title=alert.headline or alert.event or "Alerta",
                    level=alert.severity,
                    level_label=alert.level_name or alert.severity_label,
                    start_at=alert.onset_at,
                    end_at=alert.ended_at or alert.expires_at,
                    status=alert.status,
                )
            )
    if category in (None, "RISK_ESTIMATE", "DATA_QUALITY"):
        query = select(system_alerts).where(
            system_alerts.c.opened_at < end,
            or_(system_alerts.c.closed_at.is_(None), system_alerts.c.closed_at >= start),
        )
        if category is not None:
            query = query.where(system_alerts.c.category == category)
        for row in (await session.execute(query)).all():
            s = _system(row)
            entries.append(
                HistoryEntry(
                    kind="system",
                    id=s.id,
                    category=s.category,
                    category_label=s.category_label,
                    title=s.title,
                    level=s.level,
                    level_label={"CRITICAL": "Crítico", "HIGH": "Alto"}.get(s.level, "Aviso"),
                    start_at=s.opened_at,
                    end_at=s.closed_at,
                    status=s.status,
                )
            )
    entries.sort(key=lambda e: e.start_at.timestamp() if e.start_at else 0.0, reverse=True)
    offset = (page - 1) * PAGE_SIZE
    return AlertHistory(
        items=entries[offset : offset + PAGE_SIZE],
        total=len(entries),
        page=page,
        page_size=PAGE_SIZE,
        since=start,
        until=end,
    )


async def rules_info(session: AsyncSession, thresholds: Thresholds) -> RulesInfo:
    counts = dict(
        (
            await session.execute(
                select(system_alerts.c.rule_code, func.count())
                .where(system_alerts.c.closed_at.is_(None))
                .group_by(system_alerts.c.rule_code)
            )
        ).tuples()
    )
    hours = f"{thresholds.risk_stale_hours:g}".replace(".", ",")
    watched = ", ".join(WATCHED_SOURCES.values())
    return RulesInfo(
        version=RULES_VERSION,
        clear_after=thresholds.clear_after,
        rules=[
            RuleInfo(
                code="risk-subprefecture",
                category="RISK_ESTIMATE",
                description="Subprefeitura com setor de risco em alto ou crítico na estimativa "
                "mais recente do motor v0 (experimental).",
                threshold="1 setor em alto ou crítico",
                open_alerts=int(counts.get("risk-subprefecture", 0)),
            ),
            RuleInfo(
                code="source-unavailable",
                category="DATA_QUALITY",
                description=f"Fonte essencial atrasada ou indisponível: {watched}.",
                threshold="frescor STALE ou UNAVAILABLE",
                open_alerts=int(counts.get("source-unavailable", 0)),
            ),
            RuleInfo(
                code="risk-stale",
                category="DATA_QUALITY",
                description="O risco estimado não foi recalculado com sucesso recentemente.",
                threshold=f"mais de {hours} h sem cálculo",
                open_alerts=int(counts.get("risk-stale", 0)),
            ),
        ],
        note="Os alertas do sistema tratam da estimativa experimental e da saúde dos dados. "
        "Eles não são alertas oficiais, e simulações nunca geram alerta.",
    )


async def official_alert_features(session: AsyncSession, now: datetime) -> list[dict[str, Any]]:
    """Polígonos dos alertas vigentes e próximos, recortados ao município e simplificados."""
    rows = (
        await session.execute(
            text(
                """
                WITH city AS (
                    SELECT ST_Union(geom) AS g FROM subprefectures WHERE active
                )
                SELECT a.id, a.category, a.severity, a.headline, a.event, a.onset_at,
                       a.expires_at, a.ended_reason,
                       ST_AsGeoJSON(ST_SimplifyPreserveTopology(
                           CASE WHEN city.g IS NULL THEN a.geom
                                ELSE ST_Intersection(a.geom, city.g) END, 0.0005), 5) AS g
                FROM official_alerts a CROSS JOIN city
                WHERE a.msg_type <> 'Cancel' AND a.geom IS NOT NULL AND a.ended_at IS NULL
                  AND a.expires_at > :now AND a.onset_at <= :horizon
                ORDER BY a.onset_at
                """
            ),
            {"now": now, "horizon": now + UPCOMING_WINDOW},
        )
    ).all()
    features: list[dict[str, Any]] = []
    for r in rows:
        if not r.g:
            continue
        geometry = json.loads(r.g)
        if not geometry.get("coordinates"):
            continue
        features.append(
            {
                "type": "Feature",
                "id": r.id,
                "geometry": geometry,
                "properties": {
                    "id": r.id,
                    "category": r.category,
                    "category_label": CATEGORY_LABELS[r.category],
                    "severity": r.severity,
                    "severity_label": severity_label(r.severity),
                    "headline": r.headline or r.event,
                    "status": official_status(now, r.onset_at, r.expires_at, r.ended_reason),
                    "kind": "OFFICIAL",
                },
            }
        )
    return features


ALERT_ATTRIBUTION = "Alertas: Defesa Civil (IDAP/MIDR) e INMET (Alert-AS)"

"""Ingestão dos alertas (spec 009): subprefeituras, feed da IDAP e avisos do INMET.

- Subprefeituras: padrão da Fase 5 (payload bruto, normalização, desativação do que sumiu).
- Alertas oficiais: só os que atingem o município ficam, com a mensagem CAP original em
  `raw_payloads`. A interseção exata, a fração da cidade e as subprefeituras atingidas são
  calculadas no banco. A mesma coleta repetida não duplica nada (AC-142).
- `Update` e `Cancel` (INMET) encerram o alerta referenciado, mesmo que cheguem antes dele.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import case, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.core.geo import BoundingBox
from app.ingestion.geosampa_jobs import (
    _count,
    _deactivate_missing,
    _fetch_layer,
    _inserted_flag,
    _multipolygon,
    _start_result,
)
from app.ingestion.jobs import Fetcher
from app.ingestion.pipeline import IngestionContext, Job, JobResult
from app.integrations.cap import CapAlert, multipolygon, parse_cap
from app.integrations.geosampa.admin import LAYER_SUBPREFECTURES, parse_subprefectures
from app.integrations.idap.feed import read_feed
from app.integrations.inmet.warnings import color, concerns_region, parse_rss
from app.models.tables import ignored_alert_items, official_alerts, subprefectures

# Recebe a URL; devolve o corpo (ou None se a fonte não trouxe nada).
BytesFetcher = Callable[[str], Awaitable[bytes | None]]

CIVIL_DEFENSE = "CIVIL_DEFENSE"
WEATHER_WARNING = "WEATHER_WARNING"
# Uma subprefeitura conta como atingida quando o alerta cobre ao menos 5% da área dela.
SUBPREFECTURE_MIN_SHARE = 0.05
INMET_MAX_NEW_ITEMS = 80
IGNORED_RETENTION = timedelta(days=30)
DEFAULT_VALIDITY = timedelta(hours=24)


def make_subprefecture_sync_job(fetcher: Fetcher, base_url: str) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        payload, raw_id = await _fetch_layer(ctx, fetcher, base_url, LAYER_SUBPREFECTURES)
        parsed = parse_subprefectures(payload)
        result = _start_result(parsed, LAYER_SUBPREFECTURES)
        for sp in parsed.items:
            values = {
                "source_id": ctx.source_id,
                "source_code": sp.source_code,
                "name": sp.name,
                "acronym": sp.acronym,
                "region5": sp.region5,
                "geom": _multipolygon(sp.geometry),
                "active": True,
                "last_seen_at": ctx.now,
                "raw_payload_id": raw_id,
            }
            base = insert(subprefectures).values(values)
            stmt = base.on_conflict_do_update(
                index_elements=["source_id", "source_code"],
                set_={k: base.excluded[k] for k in values},
            ).returning(_inserted_flag())
            _count(result, bool((await ctx.session.execute(stmt)).scalar_one()))
        await _deactivate_missing(ctx, subprefectures, [s.source_code for s in parsed.items])
        await ctx.session.commit()
        return result

    return job


@dataclass(frozen=True)
class RegionMatch:
    intersects: bool
    approximate: bool
    city_fraction: float | None
    subprefectures: list[str]


_MATCH_SQL = text(
    """
    WITH alert AS (
        SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(
            ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)), 3)) AS g
    ),
    city AS (
        SELECT COALESCE(
            (SELECT ST_Union(geom) FROM subprefectures WHERE active),
            ST_MakeEnvelope(:lon_min, :lat_min, :lon_max, :lat_max, 4326)
        ) AS g,
        NOT EXISTS (SELECT 1 FROM subprefectures WHERE active) AS approximate
    )
    SELECT
        ST_Intersects(alert.g, city.g) AS intersects,
        city.approximate,
        CASE WHEN ST_Intersects(alert.g, city.g)
             THEN ST_Area(ST_Intersection(alert.g, city.g)::geography)
                  / NULLIF(ST_Area(city.g::geography), 0)
        END AS city_fraction,
        COALESCE((
            SELECT array_agg(s.name ORDER BY s.name)
            FROM subprefectures s
            WHERE s.active AND ST_Intersects(s.geom, alert.g)
              AND ST_Area(ST_Intersection(s.geom, alert.g)::geography)
                  >= :min_share * ST_Area(s.geom::geography)
        ), '{}') AS subprefectures
    FROM alert, city
    """
)


async def match_region(
    ctx: IngestionContext, geometry: dict[str, Any] | None, region: BoundingBox
) -> RegionMatch:
    """Interseção do alerta com o município (união das subprefeituras ou, sem elas, o retângulo)."""
    if geometry is None:
        return RegionMatch(False, False, None, [])
    row = (
        await ctx.session.execute(
            _MATCH_SQL,
            {
                "geojson": json.dumps(geometry),
                "lon_min": region.lon_min,
                "lat_min": region.lat_min,
                "lon_max": region.lon_max,
                "lat_max": region.lat_max,
                "min_share": SUBPREFECTURE_MIN_SHARE,
            },
        )
    ).one()
    fraction = float(row.city_fraction) if row.city_fraction is not None else None
    return RegionMatch(
        bool(row.intersects),
        bool(row.approximate),
        min(fraction, 1.0) if fraction is not None else None,
        list(row.subprefectures or []),
    )


def _geometry_expr(geometry: dict[str, Any] | None) -> Any:
    if geometry is None:
        return None
    return _multipolygon(geometry)


async def _store_alert(
    ctx: IngestionContext,
    alert: CapAlert,
    *,
    category: str,
    xml: str,
    request_url: str,
    item_ref: str | None,
    match: RegionMatch,
    color_hex: str | None,
    result: JobResult,
) -> None:
    raw_id = await ctx.store_raw({"cap_xml": xml}, request_url)
    geometry = multipolygon(alert)
    values = {
        "source_id": ctx.source_id,
        "category": category,
        "external_id": alert.identifier,
        "item_ref": item_ref,
        "sender_name": alert.sender_name,
        "msg_type": alert.msg_type,
        "refs": list(alert.references),
        "event": alert.event,
        "severity": alert.severity,
        "urgency": alert.urgency,
        "certainty": alert.certainty,
        "headline": alert.headline,
        "description": alert.description,
        "instruction": alert.instruction,
        "web": alert.web,
        "area_desc": alert.area_description,
        "color": color_hex,
        "sent_at": alert.sent,
        "onset_at": alert.onset or alert.sent,
        # Sem fim declarado (raro no CAP), o alerta vale 24 h a partir do envio.
        "expires_at": alert.expires or alert.sent + DEFAULT_VALIDITY,
        "geom": _geometry_expr(geometry),
        "area_approximate": match.approximate,
        "city_fraction": match.city_fraction,
        "subprefectures": match.subprefectures,
        "raw_payload_id": raw_id,
        "first_seen_at": ctx.now,
        "last_seen_at": ctx.now,
    }
    base = insert(official_alerts).values(values)
    stmt = base.on_conflict_do_update(
        index_elements=["source_id", "external_id"],
        set_={"last_seen_at": base.excluded.last_seen_at},
    ).returning(_inserted_flag())
    _count(result, bool((await ctx.session.execute(stmt)).scalar_one()))


async def apply_references(ctx: IngestionContext) -> int:
    """`Update`/`Cancel` encerram o alerta referenciado (em qualquer ordem de chegada)."""
    newer = official_alerts.alias("newer")
    stmt = (
        update(official_alerts)
        .where(
            newer.c.source_id == official_alerts.c.source_id,
            newer.c.msg_type.in_(("Update", "Cancel")),
            official_alerts.c.external_id == func.any(newer.c.refs),
            official_alerts.c.ended_at.is_(None),
        )
        .values(
            ended_at=newer.c.sent_at,
            ended_reason=case((newer.c.msg_type == "Cancel", "CANCELLED"), else_="SUPERSEDED"),
        )
    )
    result = await ctx.session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


def make_idap_job(fetch_bytes: BytesFetcher, url: str, region: BoundingBox, ibge_code: str) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        data = await fetch_bytes(url)
        if not data:
            raise ValueError("feed da IDAP vazio")
        feed = read_feed(data, region, ibge_code)
        result = JobResult(received=len(feed.alerts), rejected=len(feed.rejected))
        outside = 0
        for item in feed.alerts:
            alert = item.alert
            match = await match_region(ctx, multipolygon(alert), region)
            coded = ibge_code in alert.geocode_values("IBGE")
            if not (match.intersects or coded):
                outside += 1
                continue
            await _store_alert(
                ctx,
                alert,
                category=CIVIL_DEFENSE,
                xml=item.xml,
                request_url=url,
                item_ref=None,
                match=match,
                color_hex=None,
                result=result,
            )
        await apply_references(ctx)
        await ctx.session.commit()
        result.notes.append(
            f"{feed.total} alertas no feed; {len(feed.alerts)} perto da região; "
            f"{outside} fora do município"
        )
        result.notes.extend(f"{code}: {reason}" for code, reason in feed.rejected[:5])
        return result

    return job


async def _known_items(ctx: IngestionContext, refs: list[str]) -> set[str]:
    if not refs:
        return set()
    stored = select(official_alerts.c.item_ref).where(
        official_alerts.c.source_id == ctx.source_id, official_alerts.c.item_ref.in_(refs)
    )
    ignored = select(ignored_alert_items.c.item_ref).where(
        ignored_alert_items.c.source_id == ctx.source_id, ignored_alert_items.c.item_ref.in_(refs)
    )
    rows = await ctx.session.execute(stored.union(ignored))
    return {str(r[0]) for r in rows}


async def _ignore(ctx: IngestionContext, item_ref: str) -> None:
    await ctx.session.execute(
        insert(ignored_alert_items)
        .values(source_id=ctx.source_id, item_ref=item_ref, seen_at=ctx.now)
        .on_conflict_do_nothing()
    )


def make_inmet_job(
    fetch_bytes: BytesFetcher, rss_url: str, region: BoundingBox, ibge_code: str
) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        data = await fetch_bytes(rss_url)
        if not data:
            raise ValueError("RSS do INMET vazio")
        items = parse_rss(data)
        if not items:
            raise ValueError("RSS do INMET sem avisos")
        known = await _known_items(ctx, [i.item_id for i in items])
        pending = [i for i in items if i.item_id not in known][:INMET_MAX_NEW_ITEMS]
        result = JobResult()
        outside = 0
        for item in pending:
            try:
                body = await fetch_bytes(item.link)
                if not body:
                    raise ValueError("CAP vazio")
                alert = parse_cap(body)
            except Exception as exc:  # um aviso com problema não derruba os demais
                result.rejected += 1
                result.notes.append(f"{item.item_id}: {type(exc).__name__}: {exc}"[:200])
                continue
            result.received += 1
            if alert.status != "Actual" or not concerns_region(alert, ibge_code, region):
                outside += 1
                await _ignore(ctx, item.item_id)
                continue
            match = await match_region(ctx, multipolygon(alert), region)
            await _store_alert(
                ctx,
                alert,
                category=WEATHER_WARNING,
                xml=body.decode("utf-8", errors="replace"),
                request_url=item.link,
                item_ref=item.item_id,
                match=match,
                color_hex=color(alert),
                result=result,
            )
        await apply_references(ctx)
        await ctx.session.execute(
            delete(ignored_alert_items).where(
                ignored_alert_items.c.source_id == ctx.source_id,
                ignored_alert_items.c.seen_at < ctx.now - IGNORED_RETENTION,
            )
        )
        await ctx.session.commit()
        result.notes.insert(
            0,
            f"{len(items)} avisos no RSS; {len(pending)} novos; {outside} de outras regiões",
        )
        return result

    return job

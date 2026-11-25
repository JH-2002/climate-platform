"""Sincronização das camadas do GeoSampa (spec 005, FR-060).

Cada camada é uma fonte em `data_sources`, com sua própria `ingestion_run`. Uma resposta sem
nenhuma feição válida falha a execução e mantém os dados anteriores (nunca esvazia a base).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import func, literal_column, update
from sqlalchemy.dialects.postgresql import insert

from app.ingestion.jobs import Fetcher
from app.ingestion.pipeline import IngestionContext, Job, JobResult
from app.integrations.geosampa.wfs import (
    LAYER_FLOOD_EXTENT,
    LAYER_OCC_ALAGAMENTO,
    LAYER_OCC_INUNDACAO,
    LAYER_SECTORS,
    ParseResult,
    build_params,
    parse_flood_extents,
    parse_occurrences,
    parse_sectors,
)
from app.models.tables import flood_extent_areas, flood_occurrences, hydro_risk_sectors

# O GeoServer devolve um carimbo de hora diferente a cada requisição; sem ele, o mesmo
# conteúdo gera o mesmo hash e não é gravado de novo (FR-024).
VOLATILE_KEYS = frozenset({"timeStamp"})


def _inserted_flag() -> Any:
    return (literal_column("xmax") == 0).label("inserted")


def _multipolygon(geometry: dict[str, Any]) -> Any:
    """GeoJSON -> MultiPolygon 4326 válido (corrige autointerseções da digitalização)."""
    geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)
    return func.ST_Multi(func.ST_CollectionExtract(func.ST_MakeValid(geom), 3))


def _point(lon: float, lat: float) -> Any:
    return func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)


def request_url(base_url: str, params: dict[str, str]) -> str:
    return f"{base_url}?{urlencode(params)}"


async def _fetch_layer(
    ctx: IngestionContext, fetcher: Fetcher, base_url: str, layer: str
) -> tuple[Any, int]:
    params = build_params(layer)
    payload = await fetcher(base_url, params)
    if payload is None:
        raise ValueError(f"{layer}: a fonte não retornou conteúdo")
    stored = (
        {k: v for k, v in payload.items() if k not in VOLATILE_KEYS}
        if isinstance(payload, dict)
        else payload
    )
    raw_id = await ctx.store_raw(stored, request_url(base_url, params))
    return payload, raw_id


def _start_result(parsed: ParseResult[Any], layer: str) -> JobResult:
    if not parsed.items:
        raise ValueError(f"{layer}: nenhuma feição válida; dados anteriores mantidos")
    result = JobResult(
        received=len(parsed.items) + len(parsed.rejected), rejected=len(parsed.rejected)
    )
    result.notes.extend(f"{code}: {reason}" for code, reason in parsed.rejected[:5])
    return result


def _count(result: JobResult, inserted: bool) -> None:
    if inserted:
        result.inserted += 1
    else:
        result.updated += 1


def make_sector_sync_job(fetcher: Fetcher, base_url: str) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        payload, raw_id = await _fetch_layer(ctx, fetcher, base_url, LAYER_SECTORS)
        parsed = parse_sectors(payload)
        result = _start_result(parsed, LAYER_SECTORS)
        seen: list[str] = []
        for sector in parsed.items:
            values = {
                "source_id": ctx.source_id,
                "source_code": sector.source_code,
                "area_code": sector.area_code,
                "area_name": sector.area_name,
                "grade": sector.grade,
                "processes": list(sector.processes),
                "households": sector.households,
                "subprefecture": sector.subprefecture,
                "basin": sector.basin,
                "inspected_on": sector.inspected_on,
                "geom": _multipolygon(sector.geometry),
                "active": True,
                "first_seen_at": ctx.now,
                "last_seen_at": ctx.now,
                "raw_payload_id": raw_id,
            }
            base = insert(hydro_risk_sectors).values(values)
            stmt = base.on_conflict_do_update(
                index_elements=["source_id", "source_code"],
                set_={k: base.excluded[k] for k in values if k != "first_seen_at"},
            ).returning(_inserted_flag())
            _count(result, bool((await ctx.session.execute(stmt)).scalar_one()))
            seen.append(sector.source_code)
        await _deactivate_missing(ctx, hydro_risk_sectors, seen)
        await ctx.session.commit()
        return result

    return job


def make_flood_extent_sync_job(fetcher: Fetcher, base_url: str) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        payload, raw_id = await _fetch_layer(ctx, fetcher, base_url, LAYER_FLOOD_EXTENT)
        parsed = parse_flood_extents(payload)
        result = _start_result(parsed, LAYER_FLOOD_EXTENT)
        seen: list[str] = []
        for extent in parsed.items:
            values = {
                "source_id": ctx.source_id,
                "source_code": extent.source_code,
                "return_period_years": extent.return_period_years,
                "geom": _multipolygon(extent.geometry),
                "active": True,
                "last_seen_at": ctx.now,
                "raw_payload_id": raw_id,
            }
            base = insert(flood_extent_areas).values(values)
            stmt = base.on_conflict_do_update(
                index_elements=["source_id", "source_code"],
                set_={k: base.excluded[k] for k in values},
            ).returning(_inserted_flag())
            _count(result, bool((await ctx.session.execute(stmt)).scalar_one()))
            seen.append(extent.source_code)
        await _deactivate_missing(ctx, flood_extent_areas, seen)
        await ctx.session.commit()
        return result

    return job


def make_occurrence_sync_job(
    fetcher: Fetcher,
    base_url: str,
    layers: Iterable[str] = (LAYER_OCC_ALAGAMENTO, LAYER_OCC_INUNDACAO),
) -> Job:
    """Ocorrências não são desativadas quando somem da camada: são histórico."""

    async def job(ctx: IngestionContext) -> JobResult:
        total = JobResult()
        for layer in layers:
            payload, raw_id = await _fetch_layer(ctx, fetcher, base_url, layer)
            parsed = parse_occurrences(payload, layer)
            result = _start_result(parsed, layer)
            for occ in parsed.items:
                values = {
                    "source_id": ctx.source_id,
                    "layer": layer,
                    "source_code": occ.source_code,
                    "occurrence_type": occ.occurrence_type,
                    "occurred_on": occ.occurred_on,
                    "subprefecture": occ.subprefecture,
                    "geom": _point(occ.longitude, occ.latitude),
                    "last_seen_at": ctx.now,
                    "raw_payload_id": raw_id,
                }
                base = insert(flood_occurrences).values(values)
                stmt = base.on_conflict_do_update(
                    index_elements=["source_id", "layer", "source_code"],
                    set_={k: base.excluded[k] for k in values},
                ).returning(_inserted_flag())
                _count(result, bool((await ctx.session.execute(stmt)).scalar_one()))
            total.received += result.received
            total.inserted += result.inserted
            total.updated += result.updated
            total.rejected += result.rejected
            total.notes.extend(f"{layer}: {note}" for note in result.notes)
        await ctx.session.commit()
        return total

    return job


async def _deactivate_missing(ctx: IngestionContext, table: Any, seen: list[str]) -> None:
    await ctx.session.execute(
        update(table)
        .where(
            table.c.source_id == ctx.source_id,
            table.c.source_code.not_in(seen or [""]),
            table.c.active.is_(True),
        )
        .values(active=False)
    )

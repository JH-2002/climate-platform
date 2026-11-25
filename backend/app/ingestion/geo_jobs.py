"""Ingestão da geointeligência (spec 008): hidrografia do GeoSampa e Copernicus DEM.

Hidrografia: mesmo padrão da Fase 5 (payload bruto, normalização, desativação do que sumiu;
resposta sem feição válida falha e mantém os dados anteriores). Drenagem vem em lotes,
porque são ~28 mil trechos.

DEM: download único dos blocos (conferidos por tamanho e ETag) e recorte da região.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

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
from app.integrations.copernicus.dem import ClipInfo, clip_tiles, tile_url, tiles_for_bbox
from app.integrations.geosampa.hydro import (
    LAYER_BASINS,
    LAYER_DRAINAGE,
    LAYER_RESERVOIRS,
    parse_basins,
    parse_drainage,
    parse_reservoirs,
)
from app.models.tables import basins, dem_assets, detention_reservoirs, drainage_segments

DRAINAGE_BATCH = 500


def _multiline(geometry: dict[str, Any]) -> Any:
    geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)
    return func.ST_Multi(func.ST_CollectionExtract(func.ST_MakeValid(geom), 2))


async def _upsert(
    ctx: IngestionContext, table: Any, rows: list[dict[str, Any]], result: JobResult
) -> None:
    if not rows:
        return
    base = insert(table).values(rows)
    stmt = base.on_conflict_do_update(
        index_elements=["source_id", "source_code"],
        set_={k: base.excluded[k] for k in rows[0]},
    ).returning(_inserted_flag())
    for inserted in (await ctx.session.execute(stmt)).scalars():
        _count(result, bool(inserted))


def make_basin_sync_job(fetcher: Fetcher, base_url: str) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        payload, raw_id = await _fetch_layer(ctx, fetcher, base_url, LAYER_BASINS)
        parsed = parse_basins(payload)
        result = _start_result(parsed, LAYER_BASINS)
        rows = [
            {
                "source_id": ctx.source_id,
                "source_code": b.source_code,
                "original_code": b.original_code,
                "name": b.name,
                "main_basin": b.main_basin,
                "area_km2": b.area_km2,
                "coverage": b.coverage,
                "geom": _multipolygon(b.geometry),
                "active": True,
                "last_seen_at": ctx.now,
                "raw_payload_id": raw_id,
            }
            for b in parsed.items
        ]
        await _upsert(ctx, basins, rows, result)
        await _deactivate_missing(ctx, basins, [b.source_code for b in parsed.items])
        await ctx.session.commit()
        return result

    return job


def make_drainage_sync_job(fetcher: Fetcher, base_url: str) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        payload, raw_id = await _fetch_layer(ctx, fetcher, base_url, LAYER_DRAINAGE)
        parsed = parse_drainage(payload)
        result = _start_result(parsed, LAYER_DRAINAGE)
        rows = [
            {
                "source_id": ctx.source_id,
                "source_code": d.source_code,
                "name": d.name,
                "feature_kind": d.feature_kind,
                "course_type": d.course_type,
                "open_channel": d.open_channel,
                "length_m": d.length_m,
                "geom": _multiline(d.geometry),
                "active": True,
                "last_seen_at": ctx.now,
                "raw_payload_id": raw_id,
            }
            for d in parsed.items
        ]
        for i in range(0, len(rows), DRAINAGE_BATCH):
            await _upsert(ctx, drainage_segments, rows[i : i + DRAINAGE_BATCH], result)
        await _deactivate_missing(ctx, drainage_segments, [d.source_code for d in parsed.items])
        await ctx.session.commit()
        return result

    return job


def make_reservoir_sync_job(fetcher: Fetcher, base_url: str) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        payload, raw_id = await _fetch_layer(ctx, fetcher, base_url, LAYER_RESERVOIRS)
        parsed = parse_reservoirs(payload)
        result = _start_result(parsed, LAYER_RESERVOIRS)
        rows = [
            {
                "source_id": ctx.source_id,
                "source_code": r.source_code,
                "reservoir_code": r.reservoir_code,
                "name": r.name,
                "local_basin": r.local_basin,
                "main_basin": r.main_basin,
                "stream": r.stream,
                "volume_m3": r.volume_m3,
                "kind": r.kind,
                "emptying": r.emptying,
                "manager": r.manager,
                "realtime_monitoring": r.realtime_monitoring,
                "subprefecture": r.subprefecture,
                "built": r.built,
                "geom": _multipolygon(r.geometry),
                "active": True,
                "last_seen_at": ctx.now,
                "raw_payload_id": raw_id,
            }
            for r in parsed.items
        ]
        await _upsert(ctx, detention_reservoirs, rows, result)
        await _deactivate_missing(ctx, detention_reservoirs, [r.source_code for r in parsed.items])
        await ctx.session.commit()
        return result

    return job


# --- Copernicus DEM ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Download:
    etag: str | None
    bytes: int


# (url, destino) → ETag e tamanho gravados. Injetável: os testes gravam uma grade sintética.
Downloader = Callable[[str, Path], Awaitable[Download]]
# (blocos, caixa da região, destino) → recorte. Injetável pelo mesmo motivo.
Clipper = Callable[[Sequence[Path], tuple[float, float, float, float], Path], ClipInfo]


async def _asset(ctx: IngestionContext, kind: str, code: str) -> Any:
    return (
        await ctx.session.execute(
            select(dem_assets).where(dem_assets.c.kind == kind, dem_assets.c.code == code)
        )
    ).one_or_none()


async def _record_asset(
    ctx: IngestionContext, kind: str, code: str, now: datetime, **values: Any
) -> None:
    row = {"source_id": ctx.source_id, "kind": kind, "code": code, "created_at": now, **values}
    stmt = insert(dem_assets).values(row)
    await ctx.session.execute(
        stmt.on_conflict_do_update(
            index_elements=["kind", "code"], set_={k: stmt.excluded[k] for k in row}
        )
    )


def _present(row: Any) -> bool:
    if row is None:
        return False
    path = Path(row.path)
    return path.exists() and path.stat().st_size == row.bytes


def make_dem_job(
    downloader: Downloader,
    base_url: str,
    dem_dir: str,
    bbox: tuple[float, float, float, float],
    clip_name: str,
    clipper: Clipper = clip_tiles,
) -> Job:
    """FR-120, AC-120: baixa só o que falta e recorta só quando algum bloco mudou."""

    async def job(ctx: IngestionContext) -> JobResult:
        result = JobResult()
        tiles_dir = Path(dem_dir) / "blocos"
        tiles_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        changed = False
        for code in tiles_for_bbox(*bbox):
            result.received += 1
            path = tiles_dir / f"{code}.tif"
            paths.append(path)
            if _present(await _asset(ctx, "TILE", code)):
                continue
            url = tile_url(base_url, code)
            got = await downloader(url, path)
            await _record_asset(
                ctx, "TILE", code, ctx.now, etag=got.etag, bytes=got.bytes, path=str(path)
            )
            result.inserted += 1
            result.notes.append(f"{code}: {got.bytes / 1e6:.1f} MB baixados")
            changed = True
        clip = await _asset(ctx, "CLIP", clip_name)
        if changed or not _present(clip):
            info = clipper(paths, bbox, Path(dem_dir) / clip_name)
            await _record_asset(
                ctx,
                "CLIP",
                clip_name,
                ctx.now,
                bytes=info.bytes,
                sha256=info.sha256,
                path=str(info.path),
                resolution_m=info.resolution_m,
                bounds=info.bounds(),
            )
            result.updated += 1
            result.notes.append(
                f"recorte {info.width} × {info.height} células (~{info.resolution_m:g} m)"
            )
        await ctx.session.commit()
        return result

    return job

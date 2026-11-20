"""Reanálise diária da Open-Meteo (spec 006, FR-081, NFR-082).

- Carga inicial: um ponto por execução, desde 1991, com retomada pela `backfill_progress`.
- Atualização diária: últimos 10 dias de todos os pontos já carregados (a fonte revisa os
  dias recentes).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert

from app.ingestion.jobs import Fetcher
from app.ingestion.pipeline import IngestionContext, Job, JobResult
from app.integrations.open_meteo.archive import (
    ARCHIVE_URL,
    FIRST_DAY,
    ArchiveParseResult,
    build_params,
    parse_archive,
)
from app.integrations.open_meteo.forecast import point_key as make_point_key
from app.models.tables import backfill_progress, climate_daily

UPDATE_DAYS = 10
BATCH = 500


def _inserted_flag() -> Any:
    return (literal_column("xmax") == 0).label("inserted")


async def _store(
    ctx: IngestionContext,
    lat: float,
    lon: float,
    key: str,
    parsed: ArchiveParseResult,
    raw_id: int,
    result: JobResult,
) -> None:
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    rows = [
        {
            "source_id": ctx.source_id,
            "point_key": key,
            "point": point,
            "cell_key": parsed.cell_key,
            "day": v.day,
            "variable": v.variable,
            "value": v.value,
            "unit": v.unit,
            "kind": "MODELED",
            "raw_payload_id": raw_id,
            "ingested_at": ctx.now,
        }
        for v in parsed.values
    ]
    result.received += len(rows) + parsed.missing_values
    result.rejected += parsed.missing_values
    for start in range(0, len(rows), BATCH):
        base = insert(climate_daily).values(rows[start : start + BATCH])
        stmt = base.on_conflict_do_update(
            index_elements=["source_id", "point_key", "day", "variable"],
            set_={
                "value": base.excluded.value,
                "cell_key": base.excluded.cell_key,
                "raw_payload_id": base.excluded.raw_payload_id,
                "ingested_at": base.excluded.ingested_at,
            },
        ).returning(_inserted_flag())
        for inserted in (await ctx.session.execute(stmt)).scalars():
            if inserted:
                result.inserted += 1
            else:
                result.updated += 1


async def _fetch(
    ctx: IngestionContext, fetcher: Fetcher, lat: float, lon: float, start: date, end: date
) -> tuple[ArchiveParseResult, int]:
    params = build_params(lat, lon, start, end)
    payload = await fetcher(ARCHIVE_URL, params)
    if payload is None:
        raise ValueError("a fonte não retornou conteúdo")
    raw_id = await ctx.store_raw(payload, f"{ARCHIVE_URL}?{json.dumps(params, sort_keys=True)}")
    return parse_archive(payload), raw_id


async def pending_points(
    ctx_session: Any, source_id: int, points: Sequence[tuple[float, float]]
) -> list[tuple[float, float]]:
    """Pontos da grade cuja carga inicial ainda não terminou, na ordem da configuração."""
    done = {
        key
        for (key,) in (
            await ctx_session.execute(
                select(backfill_progress.c.point_key).where(
                    backfill_progress.c.source_id == source_id,
                    backfill_progress.c.completed.is_(True),
                )
            )
        ).tuples()
    }
    return [(lat, lon) for lat, lon in points if make_point_key(lat, lon) not in done]


def make_archive_backfill_job(
    fetcher: Fetcher, points: Sequence[tuple[float, float]], yesterday: date
) -> Job:
    """Carrega o próximo ponto pendente (um por execução, para respeitar o limite da fonte)."""

    async def job(ctx: IngestionContext) -> JobResult:
        result = JobResult()
        pending = await pending_points(ctx.session, ctx.source_id, points)
        if not pending:
            result.notes.append("carga inicial completa")
            return result
        lat, lon = pending[0]
        key = make_point_key(lat, lon)
        parsed, raw_id = await _fetch(ctx, fetcher, lat, lon, FIRST_DAY, yesterday)
        if not parsed.values:
            raise ValueError(f"{key}: resposta sem valores")
        await _store(ctx, lat, lon, key, parsed, raw_id, result)
        base = insert(backfill_progress).values(
            source_id=ctx.source_id,
            point_key=key,
            loaded_until=max(v.day for v in parsed.values),
            completed=True,
            updated_at=ctx.now,
        )
        await ctx.session.execute(
            base.on_conflict_do_update(
                index_elements=["source_id", "point_key"],
                set_={
                    "loaded_until": base.excluded.loaded_until,
                    "completed": base.excluded.completed,
                    "updated_at": base.excluded.updated_at,
                },
            )
        )
        result.notes.append(f"{key}: carga inicial ({len(pending) - 1} pontos restantes)")
        await ctx.session.commit()
        return result

    return job


def make_archive_update_job(
    fetcher: Fetcher, points: Sequence[tuple[float, float]], yesterday: date
) -> Job:
    """Atualiza os últimos dias dos pontos já carregados."""

    async def job(ctx: IngestionContext) -> JobResult:
        result = JobResult()
        pending = {
            make_point_key(*p) for p in await pending_points(ctx.session, ctx.source_id, points)
        }
        start = yesterday - timedelta(days=UPDATE_DAYS - 1)
        for lat, lon in points:
            key = make_point_key(lat, lon)
            if key in pending:
                continue
            parsed, raw_id = await _fetch(ctx, fetcher, lat, lon, start, yesterday)
            await _store(ctx, lat, lon, key, parsed, raw_id, result)
            await ctx.session.execute(
                backfill_progress.update()
                .where(
                    backfill_progress.c.source_id == ctx.source_id,
                    backfill_progress.c.point_key == key,
                )
                .values(loaded_until=yesterday, updated_at=ctx.now)
            )
        if pending:
            result.notes.append(f"pontos aguardando a carga inicial: {len(pending)}")
        await ctx.session.commit()
        return result

    return job

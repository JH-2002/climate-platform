"""Arquivo de previsões horárias de chuva (spec 015, FR-210).

Uma requisição por ponto: da data mais antiga que falta (ou dos 3 últimos dias guardados, que a
fonte revisa) até ontem.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.ingestion.jobs import Fetcher
from app.ingestion.pipeline import IngestionContext, Job, JobResult
from app.integrations.open_meteo.forecast import point_key as make_point_key
from app.integrations.open_meteo.historical_forecast import (
    FIRST_DAY,
    HISTORICAL_FORECAST_URL,
    build_params,
    parse_historical_forecast,
)
from app.models.tables import forecast_archive_hourly

REVISED_DAYS = 3
BATCH = 1000


def start_day(last_stored: date | None, first_day: date = FIRST_DAY) -> date:
    """Primeiro dia a pedir: tudo desde o começo, ou os dias recentes que a fonte revisa."""
    if last_stored is None:
        return first_day
    return max(first_day, last_stored - timedelta(days=REVISED_DAYS - 1))


def make_forecast_archive_job(
    fetcher: Fetcher, points: Sequence[tuple[float, float]], yesterday: date
) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        result = JobResult()
        t = forecast_archive_hourly
        for lat, lon in points:
            key = make_point_key(lat, lon)
            last = (
                await ctx.session.execute(
                    select(func.max(t.c.valid_at)).where(t.c.point_key == key)
                )
            ).scalar_one_or_none()
            start = start_day(last.date() if last is not None else None)
            if start > yesterday:
                continue
            # Até hoje em UTC: o dia local de ontem termina às 03 h UTC de hoje.
            params = build_params(lat, lon, start, yesterday + timedelta(days=1))
            payload = await fetcher(HISTORICAL_FORECAST_URL, params)
            if payload is None:
                raise ValueError(f"{key}: a fonte não retornou conteúdo")
            await ctx.store_raw(
                payload, f"{HISTORICAL_FORECAST_URL}?{json.dumps(params, sort_keys=True)}"
            )
            parsed = parse_historical_forecast(payload)
            result.received += len(parsed.values) + parsed.missing_values
            result.rejected += parsed.missing_values
            rows = [
                {
                    "source_id": ctx.source_id,
                    "point_key": key,
                    "valid_at": v.valid_at,
                    "precipitation_mm": v.precipitation_mm,
                    "ingested_at": ctx.now,
                }
                for v in parsed.values
            ]
            for i in range(0, len(rows), BATCH):
                base = insert(t).values(rows[i : i + BATCH])
                await ctx.session.execute(
                    base.on_conflict_do_update(
                        index_elements=["point_key", "valid_at"],
                        set_={
                            "precipitation_mm": base.excluded.precipitation_mm,
                            "ingested_at": base.excluded.ingested_at,
                        },
                    )
                )
            result.inserted += len(rows)
            result.notes.append(f"{key}: desde {start.isoformat()}")
        await ctx.session.commit()
        return result

    return job

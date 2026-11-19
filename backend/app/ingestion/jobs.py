"""Jobs de ingestão: estações do INMET (FR-021) e previsão da Open-Meteo (FR-029).

A busca é injetável (`Fetcher`), para que os testes usem respostas reais gravadas sem rede.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from sqlalchemy import func, literal_column, update
from sqlalchemy.dialects.postgresql import insert

from app.core.geo import BoundingBox
from app.ingestion.pipeline import IngestionContext, Job, JobResult
from app.integrations.inmet.stations import STATIONS_URL, parse_stations
from app.integrations.open_meteo.forecast import FORECAST_URL, build_params, parse_forecast
from app.models.tables import weather_forecasts, weather_stations

# Recebe URL e parâmetros; devolve o JSON decodificado (ou None se a fonte não trouxe nada).
Fetcher = Callable[[str, dict[str, str] | None], Awaitable[Any]]


def _point(lon: float, lat: float) -> Any:
    return func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)


def _inserted_flag() -> Any:
    # Em um upsert do PostgreSQL, xmax = 0 indica linha nova (INSERT) e != 0, atualização.
    return (literal_column("xmax") == 0).label("inserted")


def make_station_sync_job(fetcher: Fetcher, region: BoundingBox) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        payload = await fetcher(STATIONS_URL, None)
        if payload is None:
            raise ValueError("a fonte não retornou conteúdo")
        await ctx.store_raw(payload, STATIONS_URL)
        parsed = parse_stations(payload, region=region)
        result = JobResult(received=len(payload), rejected=len(parsed.rejected))
        result.notes.extend(f"{code}: {reason}" for code, reason in parsed.rejected[:5])

        seen_codes: list[str] = []
        for station in parsed.stations:
            values = {
                "source_id": ctx.source_id,
                "external_code": station.external_code,
                "name": station.name,
                "state": station.state,
                "location": _point(station.longitude, station.latitude),
                "altitude_m": station.altitude_m,
                "status": station.status,
                "source_status": station.source_status,
                "started_at": station.started_at,
                "ended_at": station.ended_at,
                "first_seen_at": ctx.now,
                "last_seen_at": ctx.now,
            }
            stmt = insert(weather_stations).values(values)
            updatable = {k: stmt.excluded[k] for k in values if k not in ("first_seen_at",)}
            stmt = stmt.on_conflict_do_update(
                index_elements=["source_id", "external_code"], set_=updatable
            ).returning(_inserted_flag())
            inserted = bool((await ctx.session.execute(stmt)).scalar_one())
            if inserted:
                result.inserted += 1
            else:
                result.updated += 1
            seen_codes.append(station.external_code)

        # Estações que sumiram da lista não são apagadas: passam a INACTIVE (FR-021).
        await ctx.session.execute(
            update(weather_stations)
            .where(
                weather_stations.c.source_id == ctx.source_id,
                weather_stations.c.external_code.not_in(seen_codes or [""]),
                weather_stations.c.status != "INACTIVE",
            )
            .values(status="INACTIVE")
        )
        await ctx.session.commit()
        return result

    return job


def make_forecast_job(fetcher: Fetcher, points: Sequence[tuple[float, float]]) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        result = JobResult()
        for lat, lon in points:
            params = build_params(lat, lon)
            payload = await fetcher(FORECAST_URL, params)
            if payload is None:
                raise ValueError("a fonte não retornou conteúdo")
            url = f"{FORECAST_URL}?{json.dumps(params, sort_keys=True)}"
            raw_id = await ctx.store_raw(payload, url)
            parsed = parse_forecast(payload)
            result.received += len(parsed.points) + parsed.missing_values
            result.rejected += parsed.missing_values
            if parsed.missing_values:
                result.notes.append(f"{parsed.point_key}: {parsed.missing_values} valores ausentes")
            for item in parsed.points:
                values = {
                    "source_id": ctx.source_id,
                    "point": _point(parsed.longitude, parsed.latitude),
                    "point_key": parsed.point_key,
                    "resolution": item.resolution,
                    "valid_at": item.valid_at,
                    "variable": item.variable,
                    "value": item.value,
                    "unit": item.unit,
                    "issued_at": ctx.now,
                    "kind": "FORECAST",
                    "mode": "REAL",
                    "raw_payload_id": raw_id,
                }
                stmt = insert(weather_forecasts).values(values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["source_id", "point_key", "resolution", "variable", "valid_at"],
                    set_={
                        "value": stmt.excluded.value,
                        "unit": stmt.excluded.unit,
                        "issued_at": stmt.excluded.issued_at,
                        "raw_payload_id": stmt.excluded.raw_payload_id,
                    },
                ).returning(_inserted_flag())
                if bool((await ctx.session.execute(stmt)).scalar_one()):
                    result.inserted += 1
                else:
                    result.updated += 1
        await ctx.session.commit()
        return result

    return job

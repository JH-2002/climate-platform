"""Geointeligência (spec 008): terreno por setor e por bacia, perfil, elevação e camadas.

O terreno é contexto e não muda o risco (BR-121). Os números do DEM vêm sempre com a fonte,
a resolução e o aviso de modelo de superfície (BR-120).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

import numpy as np
import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.geo.raster import DemRaster, clip_path, load_dem, polygon_mask, window_for_bounds
from app.geo.terrain import (
    LOW_SAMPLE_CELLS,
    bilinear,
    densify,
    gain_loss,
    line_length_m,
    relative_elevation,
    window_cells,
    zone_stats,
)
from app.integrations.copernicus.dem import ATTRIBUTION as DEM_ATTRIBUTION
from app.models.tables import basin_terrain, sector_terrain

logger = structlog.get_logger(__name__)

SURROUNDINGS_M = 1000.0
PROFILE_STEP_M = 30.0
MAX_PROFILE_KM = 20.0
MAX_PROFILE_POINTS = 10
OCCURRENCE_WINDOW_DAYS = 365
DEM_CLIP_CODE = "copernicus_glo30_regiao.tif"
TERRAIN_DISCLAIMER = (
    "Relevo do Copernicus DEM GLO-30: modelo de superfície com ~30 m de resolução. Prédios e "
    "árvores entram na elevação. Serve para comparar bairros e bacias, não ruas. É contexto: "
    "não muda a categoria de risco."
)
HYDRO_ATTRIBUTION = "Bacias, drenagem e piscinões: GeoSampa — Prefeitura de São Paulo"
BasinSort = Literal["alto", "setores", "ocorrencias", "piscinoes", "nome"]


class TerrainUnavailableError(RuntimeError):
    """O recorte do DEM ainda não existe (primeiro download pendente ou falhou)."""


# --- DEM --------------------------------------------------------------------------------------


class DemStatus(BaseModel):
    available: bool
    resolution_m: float | None
    created_at: datetime | None
    sha256: str | None
    bounds: dict[str, float] | None
    attribution: str = DEM_ATTRIBUTION
    disclaimer: str = TERRAIN_DISCLAIMER


async def dem_status(session: AsyncSession, settings: Settings) -> DemStatus:
    row = (
        await session.execute(
            text(
                "SELECT resolution_m, created_at, sha256, bounds FROM dem_assets "
                "WHERE kind = 'CLIP' AND code = :code"
            ),
            {"code": DEM_CLIP_CODE},
        )
    ).one_or_none()
    available = row is not None and clip_path(settings.dem_dir).exists()
    return DemStatus(
        available=available,
        resolution_m=row.resolution_m if row else None,
        created_at=row.created_at if row else None,
        sha256=row.sha256 if row else None,
        bounds=row.bounds if row else None,
    )


async def load_terrain(session: AsyncSession, settings: Settings) -> DemRaster | None:
    status = await dem_status(session, settings)
    if not status.available:
        return None
    return load_dem(clip_path(settings.dem_dir), status.sha256)


async def require_terrain(session: AsyncSession, settings: Settings) -> DemRaster:
    dem = await load_terrain(session, settings)
    if dem is None:
        raise TerrainUnavailableError(
            "O relevo (Copernicus DEM) ainda não foi baixado. O download de ~47 MB acontece "
            "uma vez, pela tarefa de ingestão; tente de novo em alguns minutos."
        )
    return dem


# --- cálculo do terreno (FR-122) --------------------------------------------------------------


@dataclass(frozen=True)
class TerrainSummary:
    sectors: int
    basins: int
    with_dem: bool
    outside_basins: int


_SECTOR_LINKS = text(
    """
    SELECT s.id,
           ST_AsGeoJSON(s.geom) AS geom,
           ST_XMin(s.geom) AS xmin, ST_YMin(s.geom) AS ymin,
           ST_XMax(s.geom) AS xmax, ST_YMax(s.geom) AS ymax,
           b.id AS basin_id,
           d.id AS drainage_id,
           d.dist AS drainage_m
    FROM hydro_risk_sectors s
    LEFT JOIN LATERAL (
        SELECT b.id FROM basins b
        WHERE b.active AND ST_Intersects(b.geom, s.geom)
        ORDER BY ST_Area(ST_Intersection(b.geom, s.geom)) DESC, b.id
        LIMIT 1
    ) b ON true
    LEFT JOIN LATERAL (
        SELECT d.id, ST_Distance(d.geom::geography, s.geom::geography) AS dist
        FROM drainage_segments d
        WHERE d.active
        ORDER BY d.geom <-> s.geom
        LIMIT 1
    ) d ON true
    WHERE s.active
    ORDER BY s.id
    """
)


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def sector_metrics(dem: DemRaster, row: Any) -> dict[str, Any]:
    """Elevação, declividade e elevação relativa de um setor (janela com 1 km de entorno)."""
    pad_r, pad_c = window_cells(dem.spec, SURROUNDINGS_M)
    window = window_for_bounds(dem.spec, row.xmin, row.ymin, row.xmax, row.ymax, pad_r, pad_c)
    empty = {
        "elev_median_m": None,
        "elev_min_m": None,
        "slope_mean_pct": None,
        "relative_elev_m": None,
        "cells": 0,
        "low_sample": True,
    }
    if window is None:
        return empty
    mask = polygon_mask(dem.spec, window, json.loads(row.geom))
    z = window.slice(dem.z)
    elev = zone_stats(z, mask)
    if elev.count == 0:
        return empty
    slope = zone_stats(window.slice(dem.slope), mask)
    relative = relative_elevation(z, mask, np.ones(mask.shape, dtype=bool))
    return {
        "elev_median_m": _round(elev.median),
        "elev_min_m": _round(elev.minimum),
        "slope_mean_pct": _round(slope.mean),
        "relative_elev_m": _round(relative),
        "cells": elev.count,
        "low_sample": elev.count < LOW_SAMPLE_CELLS,
    }


async def compute_terrain(
    session: AsyncSession, settings: Settings, now: datetime
) -> TerrainSummary:
    """Recalcula o terreno de todos os setores ativos e das bacias. Sem DEM, grava só a bacia
    e o curso d'água mais próximo (os números de elevação ficam vazios)."""
    dem = await load_terrain(session, settings)
    rows = list(await session.execute(_SECTOR_LINKS))
    records = []
    for row in rows:
        metrics = (
            sector_metrics(dem, row)
            if dem is not None
            else {
                "elev_median_m": None,
                "elev_min_m": None,
                "slope_mean_pct": None,
                "relative_elev_m": None,
                "cells": 0,
                "low_sample": True,
            }
        )
        records.append(
            {
                "sector_id": row.id,
                "computed_at": now,
                "dem_sha256": dem.sha256 if dem else None,
                "basin_id": row.basin_id,
                "nearest_drainage_id": row.drainage_id,
                "nearest_drainage_m": _round(row.drainage_m),
                **metrics,
            }
        )
    if records:
        stmt = insert(sector_terrain).values(records)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["sector_id"],
                set_={k: stmt.excluded[k] for k in records[0] if k != "sector_id"},
            )
        )
    basin_count = 0
    if dem is not None:
        basin_rows = list(
            await session.execute(
                text(
                    "SELECT id, ST_AsGeoJSON(geom) AS geom, ST_XMin(geom) AS xmin, "
                    "ST_YMin(geom) AS ymin, ST_XMax(geom) AS xmax, ST_YMax(geom) AS ymax "
                    "FROM basins WHERE active ORDER BY id"
                )
            )
        )
        basin_records = []
        for b in basin_rows:
            window = window_for_bounds(dem.spec, b.xmin, b.ymin, b.xmax, b.ymax)
            if window is None:
                continue
            stats = zone_stats(
                window.slice(dem.z), polygon_mask(dem.spec, window, json.loads(b.geom))
            )
            basin_records.append(
                {
                    "basin_id": b.id,
                    "computed_at": now,
                    "elev_min_m": _round(stats.minimum),
                    "elev_median_m": _round(stats.median),
                    "elev_max_m": _round(stats.maximum),
                    "cells": stats.count,
                }
            )
        if basin_records:
            stmt = insert(basin_terrain).values(basin_records)
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["basin_id"],
                    set_={k: stmt.excluded[k] for k in basin_records[0] if k != "basin_id"},
                )
            )
        basin_count = len(basin_records)
    await session.commit()
    summary = TerrainSummary(
        sectors=len(records),
        basins=basin_count,
        with_dem=dem is not None,
        outside_basins=sum(1 for r in records if r["basin_id"] is None),
    )
    logger.info("terrain_computed", **summary.__dict__)
    return summary


# --- bacias (FR-123) --------------------------------------------------------------------------


class BasinSummary(BaseModel):
    id: int
    name: str
    main_basin: str | None
    area_km2: float | None
    coverage: str | None
    sectors: int
    sectors_by_grade: dict[str, int]
    households: int | None
    high_or_above_now: int
    occurrences_12m: int
    reservoirs: int
    reservoir_volume_m3: float | None
    elev_min_m: float | None
    elev_median_m: float | None
    elev_max_m: float | None


class BasinList(BaseModel):
    items: list[BasinSummary]
    total_sectors: int
    sectors_outside_basins: int
    risk_computed_at: datetime | None
    occurrences_since: date
    attribution: str = HYDRO_ATTRIBUTION
    disclaimer: str = TERRAIN_DISCLAIMER


_BASIN_SUMMARY = """
    WITH latest AS (SELECT id, computed_at FROM risk_runs ORDER BY computed_at DESC LIMIT 1),
    sec AS (
        SELECT t.basin_id,
               count(*) AS sectors,
               count(*) FILTER (WHERE s.grade = 4) AS r4,
               count(*) FILTER (WHERE s.grade = 3) AS r3,
               count(*) FILTER (WHERE s.grade = 2) AS r2,
               count(*) FILTER (WHERE s.grade = 1) AS r1,
               sum(s.households) AS households,
               count(*) FILTER (WHERE a.category IN ('HIGH', 'CRITICAL')) AS high_now
        FROM sector_terrain t
        JOIN hydro_risk_sectors s ON s.id = t.sector_id AND s.active
        LEFT JOIN risk_assessments a
               ON a.sector_id = s.id AND a.run_id = (SELECT id FROM latest)
        GROUP BY t.basin_id
    ),
    occ AS (
        SELECT b.id AS basin_id, count(o.id) AS n
        FROM basins b JOIN flood_occurrences o ON ST_Intersects(b.geom, o.geom)
        WHERE b.active AND o.occurred_on >= :since
        GROUP BY b.id
    ),
    res AS (
        SELECT b.id AS basin_id, count(r.id) AS n, sum(r.volume_m3) AS volume
        FROM basins b JOIN detention_reservoirs r ON r.active AND ST_Intersects(b.geom, r.geom)
        WHERE b.active
        GROUP BY b.id
    )
    SELECT b.id, b.name, b.main_basin, b.area_km2, b.coverage,
           coalesce(sec.sectors, 0) AS sectors,
           coalesce(sec.r4, 0) AS r4, coalesce(sec.r3, 0) AS r3,
           coalesce(sec.r2, 0) AS r2, coalesce(sec.r1, 0) AS r1,
           sec.households,
           coalesce(sec.high_now, 0) AS high_now,
           coalesce(occ.n, 0) AS occurrences,
           coalesce(res.n, 0) AS reservoirs,
           res.volume AS reservoir_volume,
           bt.elev_min_m, bt.elev_median_m, bt.elev_max_m
    FROM basins b
    LEFT JOIN sec ON sec.basin_id = b.id
    LEFT JOIN occ ON occ.basin_id = b.id
    LEFT JOIN res ON res.basin_id = b.id
    LEFT JOIN basin_terrain bt ON bt.basin_id = b.id
    WHERE b.active {extra}
"""

_SORTS: dict[str, str] = {
    "alto": "high_now DESC, sectors DESC, b.name",
    "setores": "sectors DESC, high_now DESC, b.name",
    "ocorrencias": "occurrences DESC, sectors DESC, b.name",
    "piscinoes": "reservoir_volume DESC NULLS LAST, reservoirs DESC, b.name",
    "nome": "b.name",
}


def _basin(row: Any) -> BasinSummary:
    return BasinSummary(
        id=row.id,
        name=row.name,
        main_basin=row.main_basin,
        area_km2=row.area_km2,
        coverage=row.coverage,
        sectors=row.sectors,
        sectors_by_grade={"R4": row.r4, "R3": row.r3, "R2": row.r2, "R1": row.r1},
        households=row.households,
        high_or_above_now=row.high_now,
        occurrences_12m=row.occurrences,
        reservoirs=row.reservoirs,
        reservoir_volume_m3=row.reservoir_volume,
        elev_min_m=row.elev_min_m,
        elev_median_m=row.elev_median_m,
        elev_max_m=row.elev_max_m,
    )


def occurrences_since(now: datetime) -> date:
    return (now - timedelta(days=OCCURRENCE_WINDOW_DAYS)).date()


async def list_basins(session: AsyncSession, now: datetime, sort: BasinSort = "alto") -> BasinList:
    since = occurrences_since(now)
    sql = _BASIN_SUMMARY.format(extra="") + f" ORDER BY {_SORTS[sort]}"
    rows = list(await session.execute(text(sql), {"since": since}))
    counts = (
        await session.execute(
            text(
                "SELECT count(*) AS total, count(*) FILTER (WHERE t.basin_id IS NULL) AS outside "
                "FROM hydro_risk_sectors s JOIN sector_terrain t ON t.sector_id = s.id "
                "WHERE s.active"
            )
        )
    ).one()
    risk_at = (
        await session.execute(text("SELECT max(computed_at) FROM risk_runs"))
    ).scalar_one_or_none()
    return BasinList(
        items=[_basin(r) for r in rows],
        total_sectors=counts.total,
        sectors_outside_basins=counts.outside,
        risk_computed_at=risk_at,
        occurrences_since=since,
    )


class BasinSector(BaseModel):
    id: int
    code: str
    name: str | None
    subprefecture: str | None
    grade: int
    households: int | None
    category_now: str | None
    elev_median_m: float | None
    relative_elev_m: float | None
    nearest_drainage_m: float | None


class BasinReservoir(BaseModel):
    id: int
    name: str
    code: str | None
    volume_m3: float | None
    kind: str | None
    stream: str | None
    manager: str | None


class BasinDetail(BaseModel):
    basin: BasinSummary
    sectors: list[BasinSector]
    reservoirs: list[BasinReservoir]
    drainage_km_open: float
    drainage_km_closed: float
    occurrences_since: date
    attribution: str = HYDRO_ATTRIBUTION
    disclaimer: str = TERRAIN_DISCLAIMER


async def basin_detail(session: AsyncSession, basin_id: int, now: datetime) -> BasinDetail | None:
    since = occurrences_since(now)
    row = (
        await session.execute(
            text(_BASIN_SUMMARY.format(extra="AND b.id = :id")), {"since": since, "id": basin_id}
        )
    ).one_or_none()
    if row is None:
        return None
    sectors = await session.execute(
        text(
            """
            SELECT s.id, s.source_code AS code, s.area_name AS name, s.subprefecture, s.grade,
                   s.households, a.category AS category_now, t.elev_median_m,
                   t.relative_elev_m, t.nearest_drainage_m
            FROM sector_terrain t
            JOIN hydro_risk_sectors s ON s.id = t.sector_id AND s.active
            LEFT JOIN risk_assessments a ON a.sector_id = s.id
                 AND a.run_id = (SELECT id FROM risk_runs ORDER BY computed_at DESC LIMIT 1)
            WHERE t.basin_id = :id
            ORDER BY s.grade DESC, t.relative_elev_m NULLS LAST, s.source_code
            """
        ),
        {"id": basin_id},
    )
    reservoirs = await session.execute(
        text(
            """
            SELECT r.id, r.name, r.reservoir_code AS code, r.volume_m3, r.kind, r.stream, r.manager
            FROM detention_reservoirs r JOIN basins b ON ST_Intersects(b.geom, r.geom)
            WHERE r.active AND b.id = :id
            ORDER BY r.volume_m3 DESC NULLS LAST, r.name
            """
        ),
        {"id": basin_id},
    )
    lengths = (
        await session.execute(
            text(
                """
                SELECT coalesce(sum(ST_Length(ST_Intersection(d.geom, b.geom)::geography))
                                FILTER (WHERE d.open_channel), 0) AS open_m,
                       coalesce(sum(ST_Length(ST_Intersection(d.geom, b.geom)::geography))
                                FILTER (WHERE NOT d.open_channel), 0) AS closed_m
                FROM drainage_segments d JOIN basins b ON ST_Intersects(d.geom, b.geom)
                WHERE d.active AND b.id = :id
                """
            ),
            {"id": basin_id},
        )
    ).one()
    return BasinDetail(
        basin=_basin(row),
        sectors=[BasinSector.model_validate(r._mapping) for r in sectors],
        reservoirs=[BasinReservoir.model_validate(r._mapping) for r in reservoirs],
        drainage_km_open=round(float(lengths.open_m) / 1000, 1),
        drainage_km_closed=round(float(lengths.closed_m) / 1000, 1),
        occurrences_since=since,
    )


# --- terreno de um setor (FR-127) e de um ponto (FR-125) ---------------------------------------


class NearestDrainage(BaseModel):
    id: int
    name: str | None
    course_type: str
    open_channel: bool
    distance_m: float


class SectorTerrain(BaseModel):
    sector_id: int
    computed_at: datetime
    elev_median_m: float | None
    elev_min_m: float | None
    slope_mean_pct: float | None
    relative_elev_m: float | None
    cells: int
    low_sample: bool
    basin_id: int | None
    basin_name: str | None
    main_basin: str | None
    nearest_drainage: NearestDrainage | None
    dem_resolution_m: float | None
    attribution: str = DEM_ATTRIBUTION
    hydro_attribution: str = HYDRO_ATTRIBUTION
    disclaimer: str = TERRAIN_DISCLAIMER


async def sector_terrain_detail(session: AsyncSession, sector_id: int) -> SectorTerrain | None:
    row = (
        await session.execute(
            text(
                """
                SELECT t.*, b.name AS basin_name, b.main_basin,
                       d.name AS d_name, d.course_type AS d_type, d.open_channel AS d_open,
                       (SELECT resolution_m FROM dem_assets
                        WHERE kind = 'CLIP' AND code = :clip) AS dem_resolution_m
                FROM sector_terrain t
                LEFT JOIN basins b ON b.id = t.basin_id
                LEFT JOIN drainage_segments d ON d.id = t.nearest_drainage_id
                WHERE t.sector_id = :id
                """
            ),
            {"id": sector_id, "clip": DEM_CLIP_CODE},
        )
    ).one_or_none()
    if row is None:
        return None
    nearest = (
        NearestDrainage(
            id=row.nearest_drainage_id,
            name=row.d_name,
            course_type=row.d_type,
            open_channel=row.d_open,
            distance_m=row.nearest_drainage_m,
        )
        if row.nearest_drainage_id is not None and row.nearest_drainage_m is not None
        else None
    )
    return SectorTerrain(
        sector_id=row.sector_id,
        computed_at=row.computed_at,
        elev_median_m=row.elev_median_m,
        elev_min_m=row.elev_min_m,
        slope_mean_pct=row.slope_mean_pct,
        relative_elev_m=row.relative_elev_m,
        cells=row.cells,
        low_sample=row.low_sample,
        basin_id=row.basin_id,
        basin_name=row.basin_name,
        main_basin=row.main_basin,
        nearest_drainage=nearest,
        dem_resolution_m=row.dem_resolution_m,
    )


class PointTerrain(BaseModel):
    latitude: float
    longitude: float
    elevation_m: float | None
    slope_pct: float | None
    relative_elev_m: float | None
    basin_id: int | None
    basin_name: str | None
    nearest_drainage: NearestDrainage | None
    attribution: str = DEM_ATTRIBUTION
    disclaimer: str = TERRAIN_DISCLAIMER


async def _nearest_drainage(
    session: AsyncSession, lon: float, lat: float
) -> NearestDrainage | None:
    row = (
        await session.execute(
            text(
                """
                SELECT d.id, d.name, d.course_type, d.open_channel,
                       ST_Distance(d.geom::geography,
                                   ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist
                FROM drainage_segments d WHERE d.active
                ORDER BY d.geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
                """
            ),
            {"lon": lon, "lat": lat},
        )
    ).one_or_none()
    if row is None:
        return None
    return NearestDrainage(
        id=row.id,
        name=row.name,
        course_type=row.course_type,
        open_channel=row.open_channel,
        distance_m=round(float(row.dist), 1),
    )


async def point_terrain(
    session: AsyncSession, dem: DemRaster, lat: float, lon: float
) -> PointTerrain:
    elevation = bilinear(dem.z, dem.spec, lon, lat)
    slope = None
    relative = None
    if dem.spec.contains(lon, lat):
        r, c = dem.spec.fractional_index(lon, lat)
        ri = min(max(round(r), 0), dem.spec.height - 1)
        ci = min(max(round(c), 0), dem.spec.width - 1)
        value = float(dem.slope[ri, ci])
        slope = None if np.isnan(value) else round(value, 1)
        pad_r, pad_c = window_cells(dem.spec, SURROUNDINGS_M)
        window = window_for_bounds(dem.spec, lon, lat, lon, lat, pad_r, pad_c)
        if window is not None and elevation is not None:
            around = zone_stats(window.slice(dem.z), np.ones(window.shape, dtype=bool))
            relative = None if around.median is None else round(elevation - around.median, 1)
    basin = (
        await session.execute(
            text(
                "SELECT id, name FROM basins WHERE active AND "
                "ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
                "ORDER BY ST_Area(geom) LIMIT 1"
            ),
            {"lon": lon, "lat": lat},
        )
    ).one_or_none()
    return PointTerrain(
        latitude=lat,
        longitude=lon,
        elevation_m=_round(elevation),
        slope_pct=slope,
        relative_elev_m=relative,
        basin_id=basin.id if basin else None,
        basin_name=basin.name if basin else None,
        nearest_drainage=await _nearest_drainage(session, lon, lat),
    )


# --- perfil (FR-124) --------------------------------------------------------------------------


class ProfileError(ValueError):
    """Perfil fora dos limites (pontos, extensão ou área do relevo). Mensagem para o usuário."""


class ProfilePoint(BaseModel):
    distance_m: float
    longitude: float
    latitude: float
    elevation_m: float | None


class ProfileCrossing(BaseModel):
    kind: Literal["drainage", "sector"]
    id: int
    name: str | None
    detail: str | None
    distance_m: float
    elevation_m: float | None


class Profile(BaseModel):
    length_m: float
    samples: list[ProfilePoint]
    crossings: list[ProfileCrossing]
    elevation_min_m: float | None
    elevation_max_m: float | None
    gain_m: float
    loss_m: float
    step_m: float = PROFILE_STEP_M
    attribution: str = DEM_ATTRIBUTION
    hydro_attribution: str = HYDRO_ATTRIBUTION
    disclaimer: str = TERRAIN_DISCLAIMER


def parse_profile_points(raw: str) -> list[tuple[float, float]]:
    """ "lon,lat;lon,lat;…" → [(lon, lat), …], com limites do FR-124."""
    points: list[tuple[float, float]] = []
    for part in raw.split(";"):
        if not part.strip():
            continue
        try:
            lon_s, lat_s = part.split(",")
            points.append((float(lon_s), float(lat_s)))
        except ValueError:
            raise ProfileError(f"Ponto inválido: “{part.strip()}”. Use lon,lat;lon,lat.") from None
    if not 2 <= len(points) <= MAX_PROFILE_POINTS:
        raise ProfileError(f"O perfil precisa de 2 a {MAX_PROFILE_POINTS} pontos.")
    length = line_length_m(points)
    if length > MAX_PROFILE_KM * 1000:
        km = f"{length / 1000:.1f}".replace(".", ",")
        raise ProfileError(f"O perfil tem {km} km; o limite é {MAX_PROFILE_KM:g} km.")
    if length < PROFILE_STEP_M:
        raise ProfileError("Os pontos estão próximos demais para um perfil (menos de 30 m).")
    return points


async def profile(
    session: AsyncSession, dem: DemRaster, points: list[tuple[float, float]]
) -> Profile:
    if not all(dem.spec.contains(lon, lat) for lon, lat in points):
        raise ProfileError("Algum ponto está fora da área do relevo (região de São Paulo).")
    samples = densify(points, PROFILE_STEP_M)
    elevations = [bilinear(dem.z, dem.spec, s.longitude, s.latitude) for s in samples]
    total = samples[-1].distance_m
    wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in points) + ")"
    crossings_rows = await session.execute(
        text(
            """
            WITH l AS (SELECT ST_GeomFromText(:wkt, 4326) AS g)
            SELECT 'drainage' AS kind, d.id, d.name, d.course_type AS detail,
                   ST_LineLocatePoint(l.g, ST_PointOnSurface(ST_Intersection(d.geom, l.g))) AS f
            FROM drainage_segments d, l
            WHERE d.active AND ST_Intersects(d.geom, l.g)
            UNION ALL
            SELECT 'sector', s.id, s.source_code,
                   'R' || s.grade || coalesce(' · ' || a.category, ''),
                   ST_LineLocatePoint(l.g, ST_StartPoint(
                       ST_GeometryN(ST_CollectionExtract(ST_Intersection(s.geom, l.g), 2), 1)))
            FROM hydro_risk_sectors s CROSS JOIN l
            LEFT JOIN risk_assessments a ON a.sector_id = s.id
                 AND a.run_id = (SELECT id FROM risk_runs ORDER BY computed_at DESC LIMIT 1)
            WHERE s.active AND ST_Intersects(s.geom, l.g)
            """
        ),
        {"wkt": wkt},
    )
    crossings = []
    for c in crossings_rows:
        if c.f is None:
            continue
        distance = float(c.f) * total
        nearest = min(range(len(samples)), key=lambda i: abs(samples[i].distance_m - distance))
        crossings.append(
            ProfileCrossing(
                kind=c.kind,
                id=c.id,
                name=c.name,
                detail=c.detail,
                distance_m=round(distance, 1),
                elevation_m=_round(elevations[nearest]),
            )
        )
    crossings.sort(key=lambda c: c.distance_m)
    valid = [e for e in elevations if e is not None]
    gain, loss = gain_loss(elevations)
    return Profile(
        length_m=round(total, 1),
        samples=[
            ProfilePoint(
                distance_m=round(s.distance_m, 1),
                longitude=round(s.longitude, 6),
                latitude=round(s.latitude, 6),
                elevation_m=_round(e),
            )
            for s, e in zip(samples, elevations, strict=True)
        ],
        crossings=crossings,
        elevation_min_m=_round(min(valid)) if valid else None,
        elevation_max_m=_round(max(valid)) if valid else None,
        gain_m=round(gain, 1),
        loss_m=round(loss, 1),
    )


# --- camadas do mapa (FR-123, NFR-123) --------------------------------------------------------


async def basin_features(session: AsyncSession, now: datetime) -> list[dict[str, Any]]:
    summaries = {b.id: b for b in (await list_basins(session, now)).items}
    rows = await session.execute(
        text(
            "SELECT id, ST_AsGeoJSON(ST_Multi(ST_SimplifyPreserveTopology(geom, 0.0003)), 6) AS g "
            "FROM basins WHERE active ORDER BY id"
        )
    )
    features = []
    for row in rows:
        s = summaries.get(row.id)
        if s is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": row.id,
                "geometry": json.loads(row.g),
                "properties": {
                    "id": row.id,
                    "name": s.name,
                    "main_basin": s.main_basin,
                    "sectors": s.sectors,
                    "high_or_above_now": s.high_or_above_now,
                    "occurrences_12m": s.occurrences_12m,
                    "reservoirs": s.reservoirs,
                    "kind": "OBSERVED",
                },
            }
        )
    return features


def drainage_tolerance(zoom: float) -> float:
    if zoom < 11:
        return 0.0005
    if zoom < 13:
        return 0.0002
    return 0.00005


MAX_DRAINAGE_FEATURES = 8000


async def drainage_features(
    session: AsyncSession, bbox: tuple[float, float, float, float], zoom: float
) -> tuple[list[dict[str, Any]], bool]:
    """Trechos na área visível; abaixo do zoom 12, só os a céu aberto (NFR-123)."""
    west, south, east, north = bbox
    rows = list(
        await session.execute(
            text(
                """
                SELECT id, name, course_type, open_channel, feature_kind,
                       ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, :tol), 6) AS g
                FROM drainage_segments
                WHERE active
                  AND geom && ST_MakeEnvelope(:w, :s, :e, :n, 4326)
                  AND (:all_types OR open_channel)
                ORDER BY open_channel DESC, length_m DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {
                "tol": drainage_tolerance(zoom),
                "w": west,
                "s": south,
                "e": east,
                "n": north,
                "all_types": zoom >= 12,
                "limit": MAX_DRAINAGE_FEATURES + 1,
            },
        )
    )
    truncated = len(rows) > MAX_DRAINAGE_FEATURES
    features = [
        {
            "type": "Feature",
            "id": r.id,
            "geometry": json.loads(r.g),
            "properties": {
                "id": r.id,
                "name": r.name,
                "course_type": r.course_type,
                "open_channel": r.open_channel,
                "feature_kind": r.feature_kind,
                "kind": "OBSERVED",
            },
        }
        for r in rows[:MAX_DRAINAGE_FEATURES]
    ]
    return features, truncated


async def reservoir_features(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            """
            SELECT id, name, reservoir_code, volume_m3, kind, stream, manager, subprefecture,
                   ST_AsGeoJSON(geom, 6) AS g,
                   ST_X(ST_PointOnSurface(geom)) AS lon, ST_Y(ST_PointOnSurface(geom)) AS lat
            FROM detention_reservoirs WHERE active ORDER BY id
            """
        )
    )
    return [
        {
            "type": "Feature",
            "id": r.id,
            "geometry": {"type": "Point", "coordinates": [round(r.lon, 6), round(r.lat, 6)]},
            "properties": {
                "id": r.id,
                "name": r.name,
                "code": r.reservoir_code,
                "volume_m3": r.volume_m3,
                "kind_text": r.kind,
                "stream": r.stream,
                "manager": r.manager,
                "subprefecture": r.subprefecture,
                "kind": "OBSERVED",
            },
        }
        for r in rows
    ]

"""Relevo para o mapa e para a bacia (spec 008, Parte B).

- Blocos "terrarium" do Copernicus para o terreno 3D do MapLibre: o 3D usa o mesmo relevo dos
  cálculos (ADR-013, revisão de 2026-11-24).
- Ficha do bloco da bacia: limites, faixa de elevação e setores com a categoria real ou de uma
  simulação (com a faixa de simulação, BR-100 da spec 007).
- Relevo sombreado da bacia em PNG: a alternativa em 2D, que funciona sem WebGL (FR-131).
"""

from __future__ import annotations

import json
import threading
import uuid
from collections import OrderedDict
from typing import Any

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.png import encode_png
from app.geo.raster import (
    DemRaster,
    Window,
    polygon_mask,
    rasterize_shapes,
    window_for_bounds,
)
from app.geo.terrain import (
    GridSpec,
    hillshade,
    resample_mean,
    sample_grid,
    terrarium_rgb,
    tile_bounds,
    tile_centers,
    window_cells,
)
from app.integrations.copernicus.dem import ATTRIBUTION as DEM_ATTRIBUTION
from app.services.geo import HYDRO_ATTRIBUTION, TERRAIN_DISCLAIMER
from app.services.simulation import BANNER, HYBRID_BANNER

TILE_MIN_ZOOM = 6
TILE_MAX_ZOOM = 14
# Compressão rápida: o bloco é gerado sob demanda e fica em cache no navegador.
TILE_PNG_LEVEL = 1
TILE_CACHE_SIZE = 256
RELIEF_MAX_PX = 900
CATEGORY_CODES = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4, "UNKNOWN": 5}
# Mesmas cores das categorias no frontend (features/risk/categories.ts).
CATEGORY_RGB = {
    1: (46, 139, 87),
    2: (224, 180, 0),
    3: (232, 113, 10),
    4: (198, 40, 40),
    5: (138, 147, 155),
}


class TileError(ValueError):
    """Bloco fora da faixa de zoom ou de índices."""


_tile_lock = threading.Lock()
_tiles: OrderedDict[tuple[Any, ...], bytes] = OrderedDict()
_fill: dict[str | None, float] = {}


def _fill_value(dem: DemRaster) -> float:
    """Elevação mediana do recorte: preenche o que fica fora dele sem criar penhasco."""
    if dem.sha256 not in _fill:
        _fill[dem.sha256] = float(np.nanmedian(dem.z))
    return _fill[dem.sha256]


def terrain_tile(dem: DemRaster, zoom: int, x: int, y: int) -> bytes:
    if not TILE_MIN_ZOOM <= zoom <= TILE_MAX_ZOOM:
        raise TileError(f"zoom fora da faixa {TILE_MIN_ZOOM}–{TILE_MAX_ZOOM}")
    if not (0 <= x < 2**zoom and 0 <= y < 2**zoom):
        raise TileError("bloco fora da grade do zoom")
    west, south, east, north = tile_bounds(zoom, x, y)
    spec = dem.spec
    outside = east < spec.west or west > spec.east or north < spec.south or south > spec.north
    key = (dem.sha256, "vazio") if outside else (dem.sha256, zoom, x, y)
    with _tile_lock:
        cached = _tiles.get(key)
        if cached is not None:
            _tiles.move_to_end(key)
            return cached
    if outside:
        elevation = np.full((256, 256), np.nan, dtype=np.float32)
    else:
        lons, lats = tile_centers(zoom, x, y)
        elevation = sample_grid(dem.z, spec, lons, lats)
    png = encode_png(terrarium_rgb(elevation, _fill_value(dem)), level=TILE_PNG_LEVEL)
    with _tile_lock:
        _tiles[key] = png
        while len(_tiles) > TILE_CACHE_SIZE:
            _tiles.popitem(last=False)
    return png


# --- ficha do bloco da bacia ------------------------------------------------------------------


class BlockSector(BaseModel):
    id: int
    code: str
    name: str | None
    grade: int
    category: str
    p_high: float | None
    longitude: float
    latitude: float


class BasinBlock(BaseModel):
    basin_id: int
    name: str
    main_basin: str | None
    bounds: dict[str, float]
    elev_min_m: float | None
    elev_max_m: float | None
    source: str  # "real" ou "simulação"
    simulation_id: uuid.UUID | None
    computed_at: str | None
    banner: str | None
    sectors: list[BlockSector]
    attribution: str = DEM_ATTRIBUTION
    hydro_attribution: str = HYDRO_ATTRIBUTION
    disclaimer: str = TERRAIN_DISCLAIMER


class BlockNotFoundError(LookupError):
    """Bacia ou simulação inexistente."""


_BASIN = text(
    """
    SELECT b.id, b.name, b.main_basin,
           ST_XMin(b.geom) AS xmin, ST_YMin(b.geom) AS ymin,
           ST_XMax(b.geom) AS xmax, ST_YMax(b.geom) AS ymax,
           ST_AsGeoJSON(b.geom) AS geom,
           bt.elev_min_m, bt.elev_max_m
    FROM basins b LEFT JOIN basin_terrain bt ON bt.basin_id = b.id
    WHERE b.id = :id AND b.active
    """
)

_SECTORS_REAL = text(
    """
    SELECT s.id, s.source_code AS code, s.area_name AS name, s.grade,
           coalesce(a.category, 'UNKNOWN') AS category, NULL::float AS p_high,
           ST_X(ST_PointOnSurface(s.geom)) AS longitude,
           ST_Y(ST_PointOnSurface(s.geom)) AS latitude,
           ST_AsGeoJSON(s.geom) AS geom
    FROM sector_terrain t
    JOIN hydro_risk_sectors s ON s.id = t.sector_id AND s.active
    LEFT JOIN risk_assessments a ON a.sector_id = s.id
         AND a.run_id = (SELECT id FROM risk_runs ORDER BY computed_at DESC LIMIT 1)
    WHERE t.basin_id = :id
    ORDER BY s.id
    """
)

_SECTORS_SIMULATED = text(
    """
    SELECT s.id, s.source_code AS code, s.area_name AS name, s.grade,
           r.category, r.p_high,
           ST_X(ST_PointOnSurface(s.geom)) AS longitude,
           ST_Y(ST_PointOnSurface(s.geom)) AS latitude,
           ST_AsGeoJSON(s.geom) AS geom
    FROM sector_terrain t
    JOIN hydro_risk_sectors s ON s.id = t.sector_id
    JOIN simulation_results r ON r.sector_id = s.id AND r.run_id = :run
    WHERE t.basin_id = :id
    ORDER BY s.id
    """
)


async def _basin_row(session: AsyncSession, basin_id: int) -> Any:
    row = (await session.execute(_BASIN, {"id": basin_id})).one_or_none()
    if row is None:
        raise BlockNotFoundError("Bacia não encontrada.")
    return row


async def _sector_rows(
    session: AsyncSession, basin_id: int, simulation_id: uuid.UUID | None
) -> tuple[list[Any], str | None, str | None]:
    """Setores da bacia com a categoria real (última estimativa) ou da simulação."""
    if simulation_id is None:
        at = (
            await session.execute(text("SELECT max(computed_at) FROM risk_runs"))
        ).scalar_one_or_none()
        rows = list(await session.execute(_SECTORS_REAL, {"id": basin_id}))
        return rows, None if at is None else at.isoformat(), None
    run = (
        await session.execute(
            text("SELECT mode, created_at FROM simulation_runs WHERE id = :run"),
            {"run": simulation_id},
        )
    ).one_or_none()
    if run is None:
        raise BlockNotFoundError("Simulação não encontrada. Elas ficam guardadas por 30 dias.")
    rows = list(await session.execute(_SECTORS_SIMULATED, {"id": basin_id, "run": simulation_id}))
    banner = HYBRID_BANNER if run.mode == "HYBRID" else BANNER
    return rows, run.created_at.isoformat(), banner


async def basin_block(
    session: AsyncSession, basin_id: int, simulation_id: uuid.UUID | None
) -> BasinBlock:
    basin = await _basin_row(session, basin_id)
    rows, at, banner = await _sector_rows(session, basin_id, simulation_id)
    return BasinBlock(
        basin_id=basin.id,
        name=basin.name,
        main_basin=basin.main_basin,
        bounds={"west": basin.xmin, "south": basin.ymin, "east": basin.xmax, "north": basin.ymax},
        elev_min_m=basin.elev_min_m,
        elev_max_m=basin.elev_max_m,
        source="real" if simulation_id is None else "simulação",
        simulation_id=simulation_id,
        computed_at=at,
        banner=banner,
        sectors=[
            BlockSector(
                id=r.id,
                code=r.code,
                name=r.name,
                grade=r.grade,
                category=r.category,
                p_high=r.p_high,
                longitude=round(r.longitude, 6),
                latitude=round(r.latitude, 6),
            )
            for r in rows
        ],
    )


# --- relevo sombreado em PNG (alternativa 2D) -------------------------------------------------

# Cores hipsométricas: várzea (verde), meia encosta (bege), topo (marrom).
_TINT = np.array([[167, 199, 154], [232, 216, 168], [176, 139, 94]], dtype=np.float64)


def _tint(elevation: npt.NDArray[np.float32], low: float, high: float) -> npt.NDArray[np.float64]:
    span = max(high - low, 1.0)
    t = np.clip((np.nan_to_num(elevation, nan=low) - low) / span, 0, 1)[..., None]
    first = _TINT[0] + (_TINT[1] - _TINT[0]) * np.clip(t * 2, 0, 1)
    second = _TINT[1] + (_TINT[2] - _TINT[1]) * np.clip(t * 2 - 1, 0, 1)
    out: npt.NDArray[np.float64] = np.where(t < 0.5, first, second)
    return out


def _paint(
    rgb: npt.NDArray[np.float64], mask: npt.NDArray[np.bool_], color: tuple[int, ...]
) -> None:
    rgb[mask] = color


async def basin_relief_png(
    session: AsyncSession,
    dem: DemRaster,
    basin_id: int,
    simulation_id: uuid.UUID | None,
    max_px: int = RELIEF_MAX_PX,
) -> bytes:
    basin = await _basin_row(session, basin_id)
    sectors, _, _ = await _sector_rows(session, basin_id, simulation_id)
    pad_r, pad_c = window_cells(dem.spec, 300)
    window = window_for_bounds(
        dem.spec, basin.xmin, basin.ymin, basin.xmax, basin.ymax, pad_r, pad_c
    )
    if window is None:
        raise BlockNotFoundError("Bacia fora da área do relevo.")
    z = window.slice(dem.z)
    small, factor = resample_mean(z, max_px)
    spec = GridSpec(
        west=dem.spec.west + window.c0 * dem.spec.dlon,
        north=dem.spec.north - window.r0 * dem.spec.dlat,
        dlon=dem.spec.dlon * factor,
        dlat=dem.spec.dlat * factor,
        width=small.shape[1],
        height=small.shape[0],
    )
    dx, dy = spec.cell_size_m()
    finite = small[np.isfinite(small)]
    low = float(basin.elev_min_m if basin.elev_min_m is not None else finite.min())
    high = float(basin.elev_max_m if basin.elev_max_m is not None else finite.max())
    shade = hillshade(np.nan_to_num(small, nan=low), dx, dy)
    rgb = _tint(small, low, high) * (0.55 + 0.45 * shade[..., None])

    basin_geom = json.loads(basin.geom)
    inside = polygon_mask(spec, Window(0, spec.height, 0, spec.width), basin_geom)
    rgb[~inside] = rgb[~inside] * 0.45 + 255 * 0.55  # fora da bacia: esmaecido

    drainage = await session.execute(
        text(
            """
            SELECT ST_AsGeoJSON(ST_Intersection(d.geom, b.geom)) AS g, d.open_channel
            FROM drainage_segments d JOIN basins b ON b.id = :id
            WHERE d.active AND d.geom && b.geom AND ST_Intersects(d.geom, b.geom)
            """
        ),
        {"id": basin_id},
    )
    lines = [(json.loads(r.g), 1 if r.open_channel else 2) for r in drainage]
    drawn = rasterize_shapes(spec, lines)
    _paint(rgb, drawn == 2, (123, 143, 166))
    _paint(rgb, drawn == 1, (29, 111, 214))

    reservoirs = await session.execute(
        text(
            """
            SELECT ST_AsGeoJSON(r.geom) AS g FROM detention_reservoirs r JOIN basins b ON b.id = :id
            WHERE r.active AND ST_Intersects(r.geom, b.geom)
            """
        ),
        {"id": basin_id},
    )
    _paint(
        rgb, rasterize_shapes(spec, [(json.loads(r.g), 1) for r in reservoirs]) == 1, (15, 118, 110)
    )

    sector_codes = rasterize_shapes(
        spec, [(json.loads(r.geom), CATEGORY_CODES.get(r.category, 5)) for r in sectors]
    )
    for code, color in CATEGORY_RGB.items():
        _paint(rgb, sector_codes == code, color)

    outline = await session.execute(
        text("SELECT ST_AsGeoJSON(ST_Boundary(geom)) AS g FROM basins WHERE id = :id"),
        {"id": basin_id},
    )
    edge = rasterize_shapes(spec, [(json.loads(r.g), 1) for r in outline])
    _paint(rgb, edge == 1, (11, 92, 122))
    return encode_png(np.clip(rgb, 0, 255).astype(np.uint8))

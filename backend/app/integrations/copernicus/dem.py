"""Copernicus DEM GLO-30: blocos de 1° por HTTPS e recorte da região (spec 008, FR-120).

Bucket público confirmado em 2026-11-20 (SOURCES.md §13): cada bloco é um GeoTIFF otimizado
(COG) de float32, com grade de 1" em latitude. O nome usa o canto sudoeste do bloco:
`Copernicus_DSM_COG_10_S24_00_W047_00_DEM` cobre de -24° a -23° e de -47° a -46°.

O recorte usa rasterio, importado só dentro da função (o resto do módulo é puro).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

TILE_PREFIX = "Copernicus_DSM_COG_10"
# Folga em volta da região: o entorno de 1 km dos setores da borda continua dentro do recorte.
CLIP_MARGIN_DEG = 0.02
ATTRIBUTION = (
    "Produced using Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space "
    "GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA, all rights reserved"
)


def tile_code(lat_floor: int, lon_floor: int) -> str:
    ns = "S" if lat_floor < 0 else "N"
    ew = "W" if lon_floor < 0 else "E"
    return f"{TILE_PREFIX}_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def tiles_for_bbox(west: float, south: float, east: float, north: float) -> list[str]:
    """Blocos que cobrem a caixa (com a folga do recorte), do noroeste para o sudeste."""
    w, s = west - CLIP_MARGIN_DEG, south - CLIP_MARGIN_DEG
    e, n = east + CLIP_MARGIN_DEG, north + CLIP_MARGIN_DEG
    lats = range(math.floor(n - 1e-9), math.floor(s) - 1, -1)
    lons = range(math.floor(w), math.floor(e - 1e-9) + 1)
    return [tile_code(lat, lon) for lat in lats for lon in lons]


def tile_url(base_url: str, code: str) -> str:
    return f"{base_url.rstrip('/')}/{code}/{code}.tif"


@dataclass(frozen=True)
class ClipInfo:
    path: Path
    width: int
    height: int
    west: float
    north: float
    dlon: float
    dlat: float
    bytes: int
    sha256: str
    resolution_m: float

    def bounds(self) -> dict[str, float]:
        return {
            "west": self.west,
            "north": self.north,
            "east": self.west + self.dlon * self.width,
            "south": self.north - self.dlat * self.height,
        }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clip_tiles(
    tile_paths: Sequence[Path],
    bbox: tuple[float, float, float, float],
    out_path: Path,
) -> ClipInfo:
    """Junta os blocos e recorta a região com folga; grava GeoTIFF float32 comprimido."""
    import rasterio
    from rasterio.merge import merge

    west, south, east, north = bbox
    bounds = (
        west - CLIP_MARGIN_DEG,
        south - CLIP_MARGIN_DEG,
        east + CLIP_MARGIN_DEG,
        north + CLIP_MARGIN_DEG,
    )
    sources = [rasterio.open(p) for p in tile_paths]
    try:
        mosaic, transform = merge(sources, bounds=bounds, nodata=float("nan"), dtype="float32")
        profile = sources[0].profile.copy()
    finally:
        for src in sources:
            src.close()
    profile.update(
        driver="GTiff",
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        count=1,
        dtype="float32",
        nodata=float("nan"),
        transform=transform,
        compress="deflate",
        predictor=3,
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.tif")
    with rasterio.open(tmp, "w", **profile) as dst:
        dst.write(mosaic[0].astype("float32"), 1)
    tmp.replace(out_path)
    dlon, dlat = float(transform.a), float(-transform.e)
    mid = math.radians(north - (north - south) / 2)
    return ClipInfo(
        path=out_path,
        width=int(mosaic.shape[2]),
        height=int(mosaic.shape[1]),
        west=float(transform.c),
        north=float(transform.f),
        dlon=dlon,
        dlat=dlat,
        bytes=out_path.stat().st_size,
        sha256=sha256_of(out_path),
        resolution_m=round(min(dlat * 111_195.0, dlon * 111_195.0 * math.cos(mid)), 1),
    )

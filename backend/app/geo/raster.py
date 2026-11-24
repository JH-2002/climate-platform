"""Leitura do recorte do DEM e máscaras de polígonos (rasterio). Sem regra de negócio.

O recorte inteiro (~2.400 × 2.400 células float32, ~23 MB) fica em memória por processo e é
recarregado quando o arquivo muda.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.geo.terrain import Grid, GridSpec, Mask, slope_percent

DEM_CLIP_NAME = "copernicus_glo30_regiao.tif"


@dataclass
class DemRaster:
    z: Grid
    spec: GridSpec
    sha256: str | None = None
    _slope: Grid | None = field(default=None, repr=False)

    @property
    def slope(self) -> Grid:
        if self._slope is None:
            dx, dy = self.spec.cell_size_m()
            self._slope = slope_percent(self.z, dx, dy)
        return self._slope


@dataclass(frozen=True)
class Window:
    """Janela [r0, r1) × [c0, c1) dentro da grade."""

    r0: int
    r1: int
    c0: int
    c1: int

    def slice(self, grid: Grid) -> Grid:
        return grid[self.r0 : self.r1, self.c0 : self.c1]

    @property
    def shape(self) -> tuple[int, int]:
        return self.r1 - self.r0, self.c1 - self.c0


_lock = threading.Lock()
_cache: dict[str, tuple[float, DemRaster]] = {}


def clip_path(dem_dir: str) -> Path:
    return Path(dem_dir) / DEM_CLIP_NAME


def load_dem(path: Path, sha256: str | None = None) -> DemRaster | None:
    """Recorte em memória; None se o arquivo ainda não existe (DEM não baixado)."""
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    key = str(path)
    with _lock:
        cached = _cache.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        import rasterio

        with rasterio.open(path) as src:
            z = src.read(1, out_dtype="float32")
            nodata = src.nodata
            t = src.transform
        if nodata is not None and not np.isnan(nodata):
            z[z == nodata] = np.nan
        spec = GridSpec(
            west=float(t.c),
            north=float(t.f),
            dlon=float(t.a),
            dlat=float(-t.e),
            width=int(z.shape[1]),
            height=int(z.shape[0]),
        )
        raster = DemRaster(z=z, spec=spec, sha256=sha256)
        _cache[key] = (mtime, raster)
        return raster


def window_for_bounds(
    spec: GridSpec,
    west: float,
    south: float,
    east: float,
    north: float,
    pad_rows: int = 0,
    pad_cols: int = 0,
) -> Window | None:
    """Janela que cobre a caixa (com folga em células); None se cair fora da grade."""
    r0 = int(np.floor((spec.north - north) / spec.dlat)) - pad_rows
    r1 = int(np.ceil((spec.north - south) / spec.dlat)) + pad_rows
    c0 = int(np.floor((west - spec.west) / spec.dlon)) - pad_cols
    c1 = int(np.ceil((east - spec.west) / spec.dlon)) + pad_cols
    r0, c0 = max(r0, 0), max(c0, 0)
    r1, c1 = min(r1, spec.height), min(c1, spec.width)
    if r0 >= r1 or c0 >= c1:
        return None
    return Window(r0, r1, c0, c1)


def polygon_mask(spec: GridSpec, window: Window, geometry: dict[str, Any]) -> Mask:
    """Células da janela cujo centro cai no polígono; se nenhuma, as que ele toca.

    Setores pequenos (menos de uma célula de 30 m) ficariam sem amostra pelo centro.
    """
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin

    transform = from_origin(
        spec.west + window.c0 * spec.dlon,
        spec.north - window.r0 * spec.dlat,
        spec.dlon,
        spec.dlat,
    )
    mask: Mask = geometry_mask([geometry], out_shape=window.shape, transform=transform, invert=True)
    if not mask.any():
        mask = geometry_mask(
            [geometry], out_shape=window.shape, transform=transform, invert=True, all_touched=True
        )
    return mask

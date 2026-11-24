"""Cálculos de terreno sobre grades numpy (NFR-120). Puro: sem arquivo, banco ou rasterio.

A grade é a do DEM em graus (lon/lat, WGS84). As distâncias e a declividade usam o tamanho
da célula em metros na latitude da grade, o que basta para a extensão da cidade (~70 km).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.risk.geo import EARTH_RADIUS_KM, haversine_km

Grid = npt.NDArray[np.float32]
Mask = npt.NDArray[np.bool_]

M_PER_DEG_LAT = math.pi * EARTH_RADIUS_KM * 1000 / 180
# Setores com menos células que isso têm estatística frágil (spec 008, riscos).
LOW_SAMPLE_CELLS = 4


@dataclass(frozen=True)
class GridSpec:
    """Grade regular: canto noroeste e passo em graus (dlat positivo, linhas para o sul)."""

    west: float
    north: float
    dlon: float
    dlat: float
    width: int
    height: int

    @property
    def east(self) -> float:
        return self.west + self.dlon * self.width

    @property
    def south(self) -> float:
        return self.north - self.dlat * self.height

    def fractional_index(self, lon: float, lat: float) -> tuple[float, float]:
        """(linha, coluna) do ponto, com o centro da célula em .5 → índice inteiro."""
        return (self.north - lat) / self.dlat - 0.5, (lon - self.west) / self.dlon - 0.5

    def contains(self, lon: float, lat: float) -> bool:
        return self.west <= lon <= self.east and self.south <= lat <= self.north

    def cell_size_m(self) -> tuple[float, float]:
        mid = math.radians((self.north + self.south) / 2)
        return self.dlon * M_PER_DEG_LAT * math.cos(mid), self.dlat * M_PER_DEG_LAT


@dataclass(frozen=True)
class ZoneStats:
    count: int
    median: float | None
    minimum: float | None
    maximum: float | None
    mean: float | None


def slope_percent(z: Grid, dx: float, dy: float) -> Grid:
    """Declividade em % pelo método de Horn (3 × 3). Bordas e vizinhanças com vazio → NaN."""
    out = np.full(z.shape, np.nan, dtype=np.float32)
    if z.shape[0] < 3 or z.shape[1] < 3:
        return out
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    out[1:-1, 1:-1] = np.sqrt(dzdx**2 + dzdy**2) * 100
    return out


def zone_stats(values: Grid, mask: Mask) -> ZoneStats:
    selected = values[mask]
    selected = selected[np.isfinite(selected)]
    if selected.size == 0:
        return ZoneStats(0, None, None, None, None)
    return ZoneStats(
        count=int(selected.size),
        median=float(np.median(selected)),
        minimum=float(selected.min()),
        maximum=float(selected.max()),
        mean=float(selected.mean()),
    )


def relative_elevation(zone: Grid, zone_mask: Mask, surroundings: Mask) -> float | None:
    """Mediana da zona menos a mediana do entorno (sem a zona). Negativo = mais baixo."""
    inner = zone_stats(zone, zone_mask)
    ring = zone_stats(zone, surroundings & ~zone_mask)
    if inner.median is None or ring.median is None:
        return None
    return inner.median - ring.median


def window_cells(spec: GridSpec, meters: float) -> tuple[int, int]:
    """Quantas células cobrem `meters` em linhas e colunas."""
    dx, dy = spec.cell_size_m()
    return max(1, math.ceil(meters / dy)), max(1, math.ceil(meters / dx))


def bilinear(z: Grid, spec: GridSpec, lon: float, lat: float) -> float | None:
    if not spec.contains(lon, lat):
        return None
    r, c = spec.fractional_index(lon, lat)
    r = min(max(r, 0.0), spec.height - 1.0)
    c = min(max(c, 0.0), spec.width - 1.0)
    r0, c0 = math.floor(r), math.floor(c)
    r1, c1 = min(r0 + 1, spec.height - 1), min(c0 + 1, spec.width - 1)
    fr, fc = r - r0, c - c0
    corners = np.array([z[r0, c0], z[r0, c1], z[r1, c0], z[r1, c1]], dtype=np.float64)
    if not np.all(np.isfinite(corners)):
        return None
    top = corners[0] * (1 - fc) + corners[1] * fc
    bottom = corners[2] * (1 - fc) + corners[3] * fc
    return float(top * (1 - fr) + bottom * fr)


@dataclass(frozen=True)
class ProfileSample:
    distance_m: float
    longitude: float
    latitude: float


def densify(points: Sequence[tuple[float, float]], step_m: float) -> list[ProfileSample]:
    """Amostras a cada `step_m` ao longo da linha (lon, lat), incluindo os vértices."""
    samples = [ProfileSample(0.0, points[0][0], points[0][1])]
    covered = 0.0
    for (lon1, lat1), (lon2, lat2) in itertools.pairwise(points):
        length = haversine_km(lat1, lon1, lat2, lon2) * 1000
        steps = max(1, math.ceil(length / step_m))
        for k in range(1, steps + 1):
            t = k / steps
            samples.append(
                ProfileSample(
                    distance_m=covered + length * t,
                    longitude=lon1 + (lon2 - lon1) * t,
                    latitude=lat1 + (lat2 - lat1) * t,
                )
            )
        covered += length
    return samples


def line_length_m(points: Sequence[tuple[float, float]]) -> float:
    return sum(
        haversine_km(lat1, lon1, lat2, lon2) * 1000
        for (lon1, lat1), (lon2, lat2) in itertools.pairwise(points)
    )


def gain_loss(elevations: Sequence[float | None]) -> tuple[float, float]:
    """Soma das subidas e das descidas entre amostras válidas consecutivas."""
    valid = [e for e in elevations if e is not None]
    gain = sum(max(0.0, b - a) for a, b in itertools.pairwise(valid))
    loss = sum(max(0.0, a - b) for a, b in itertools.pairwise(valid))
    return gain, loss

"""T123 — cálculos de terreno em grades sintéticas com resposta conhecida."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from app.geo.terrain import (
    GridSpec,
    bilinear,
    densify,
    gain_loss,
    line_length_m,
    relative_elevation,
    slope_percent,
    window_cells,
    zone_stats,
)

ARCSEC = 1 / 3600
SPEC = GridSpec(west=-46.70, north=-23.50, dlon=ARCSEC, dlat=ARCSEC, width=60, height=50)


def test_cell_size_near_sao_paulo() -> None:
    dx, dy = SPEC.cell_size_m()
    assert dy == pytest.approx(30.9, abs=0.1)
    assert dx == pytest.approx(28.3, abs=0.2)  # encolhe com o cosseno da latitude


def test_slope_of_inclined_plane() -> None:
    """Plano que sobe 10 m a cada 100 m para leste → 10% em todo o interior."""
    dx, dy = 30.0, 30.0
    cols = np.arange(20, dtype=np.float32)
    z = np.tile(cols * dx * 0.10, (10, 1)).astype(np.float32)
    slope = slope_percent(z, dx, dy)
    assert np.isnan(slope[0]).all() and np.isnan(slope[:, 0]).all()
    assert np.allclose(slope[1:-1, 1:-1], 10.0, atol=1e-4)


def test_slope_nan_propagates_from_voids() -> None:
    z = np.zeros((5, 5), dtype=np.float32)
    z[2, 2] = np.nan
    slope = slope_percent(z, 30.0, 30.0)
    neighbours = slope[1:4, 1:4].copy()
    neighbours[1, 1] = np.nan  # o método de Horn não usa a célula central
    assert np.isnan(neighbours).all()


def test_zone_stats_ignore_voids() -> None:
    values = np.array([[1, 2, np.nan], [4, 5, 6]], dtype=np.float32)
    mask = np.array([[True, True, True], [False, True, False]])
    stats = zone_stats(values, mask)
    assert (stats.count, stats.median, stats.minimum, stats.maximum) == (3, 2.0, 1.0, 5.0)
    assert zone_stats(values, np.zeros_like(mask)).median is None


def test_relative_elevation_of_valley_floor() -> None:
    """Vale em V: o fundo fica abaixo do entorno; a encosta, acima do fundo."""
    cols = np.abs(np.arange(-10, 11, dtype=np.float32)) * 3.0 + 700
    z = np.tile(cols, (21, 1)).astype(np.float32)
    floor = np.zeros(z.shape, dtype=bool)
    floor[8:13, 9:12] = True
    everything = np.ones(z.shape, dtype=bool)
    rel = relative_elevation(z, floor, everything)
    assert rel is not None and rel < -10
    slope_side = np.zeros(z.shape, dtype=bool)
    slope_side[8:13, 18:21] = True
    rel_side = relative_elevation(z, slope_side, everything)
    assert rel_side is not None and rel_side > 0


def test_window_cells_for_one_km() -> None:
    rows, cols = window_cells(SPEC, 1000)
    assert rows == 33 and cols == 36


def test_bilinear_on_cell_centers_and_between() -> None:
    z = np.arange(SPEC.width * SPEC.height, dtype=np.float32).reshape(SPEC.height, SPEC.width)
    center_lon = SPEC.west + SPEC.dlon * 10.5
    center_lat = SPEC.north - SPEC.dlat * 4.5
    assert bilinear(z, SPEC, center_lon, center_lat) == pytest.approx(z[4, 10])
    between = bilinear(z, SPEC, center_lon + SPEC.dlon / 2, center_lat)
    assert between == pytest.approx((z[4, 10] + z[4, 11]) / 2)
    assert bilinear(z, SPEC, -40.0, -23.5) is None


def test_densify_and_length() -> None:
    line = [(-46.65, -23.55), (-46.64, -23.55), (-46.64, -23.56)]
    total = line_length_m(line)
    samples = densify(line, 30.0)
    assert samples[0].distance_m == 0.0
    assert samples[-1].distance_m == pytest.approx(total)
    gaps = [b.distance_m - a.distance_m for a, b in itertools.pairwise(samples)]
    assert max(gaps) <= 30.0 + 1e-6
    assert (samples[-1].longitude, samples[-1].latitude) == (-46.64, -23.56)


def test_gain_and_loss_skip_gaps() -> None:
    assert gain_loss([700, 710, None, 705, 720]) == (25.0, 5.0)

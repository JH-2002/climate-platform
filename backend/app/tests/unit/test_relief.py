"""Spec 008, Parte B — blocos de relevo (terrarium), sombreamento, reamostragem e PNG."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.geo.png import decode_png, encode_png
from app.geo.terrain import (
    GridSpec,
    bilinear,
    hillshade,
    resample_mean,
    sample_grid,
    terrarium_decode,
    terrarium_rgb,
    tile_bounds,
    tile_centers,
)

ARCSEC = 1 / 3600
SPEC = GridSpec(west=-46.70, north=-23.50, dlon=ARCSEC, dlat=ARCSEC, width=60, height=50)


def test_terrarium_round_trip_keeps_centimetres() -> None:
    heights = np.array([[715.25, 1221.0], [-3.5, np.nan]], dtype=np.float32)
    decoded = terrarium_decode(terrarium_rgb(heights, fill=760.0))
    assert decoded[0, 0] == pytest.approx(715.25, abs=0.004)
    assert decoded[0, 1] == pytest.approx(1221.0, abs=0.004)
    assert decoded[1, 0] == pytest.approx(-3.5, abs=0.004)
    assert decoded[1, 1] == pytest.approx(760.0)  # vazio recebe o valor de preenchimento


def test_tile_bounds_and_centers() -> None:
    west, south, east, north = tile_bounds(0, 0, 0)
    assert (west, east) == (-180, 180) and north == pytest.approx(85.0511, abs=1e-4)
    assert south == pytest.approx(-85.0511, abs=1e-4)
    # bloco z12 que contém a Praça da Sé
    z, lon, lat = 12, -46.6333, -23.5505
    x = int((lon + 180) / 360 * 2**z)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**z)
    w, s, e, n = tile_bounds(z, x, y)
    assert w <= lon <= e and s <= lat <= n
    lons, lats = tile_centers(z, x, y, size=8)
    assert (
        lons.shape == (8, 8) and np.all((lons > w) & (lons < e)) and np.all((lats > s) & (lats < n))
    )
    assert lats[0, 0] > lats[-1, 0]  # primeira linha é a do norte


def test_sample_grid_matches_scalar_bilinear() -> None:
    rng = np.random.default_rng(1)
    z = rng.uniform(700, 800, size=(SPEC.height, SPEC.width)).astype(np.float32)
    lons = np.array([[-46.695, -46.69], [-46.6855, -40.0]])
    lats = np.array([[-23.505, -23.507], [-23.5101, -23.5]])
    sampled = sample_grid(z, SPEC, lons, lats)
    for i in range(2):
        for j in range(2):
            expected = bilinear(z, SPEC, float(lons[i, j]), float(lats[i, j]))
            if expected is None:
                assert np.isnan(sampled[i, j])
            else:
                assert sampled[i, j] == pytest.approx(expected, rel=1e-5)


def test_hillshade_of_flat_ground_is_constant() -> None:
    flat = np.full((10, 10), 750, dtype=np.float32)
    assert np.allclose(hillshade(flat, 30, 30), math.sin(math.radians(45)), atol=1e-6)


def test_hillshade_lights_northwest_slopes() -> None:
    rows = np.arange(20, dtype=np.float32)[:, None]
    facing_north = np.tile(rows * 5, (1, 20)).astype(np.float32)  # sobe para o sul: face norte
    facing_south = facing_north[::-1].copy()
    assert hillshade(facing_north, 30, 30).mean() > hillshade(facing_south, 30, 30).mean()


def test_resample_mean_shrinks_and_ignores_voids() -> None:
    z = np.arange(36, dtype=np.float32).reshape(6, 6)
    z[0, 0] = np.nan
    out, factor = resample_mean(z, 3)
    assert factor == 2 and out.shape == (3, 3)
    assert out[0, 0] == pytest.approx((1 + 6 + 7) / 3)
    assert out[2, 2] == pytest.approx((28 + 29 + 34 + 35) / 4)
    same, one = resample_mean(z, 10)
    assert one == 1 and same.shape == z.shape


def test_png_round_trip_rgb_and_rgba() -> None:
    rgb = np.random.default_rng(2).integers(0, 256, size=(7, 5, 3), dtype=np.uint8)
    rgba = np.random.default_rng(3).integers(0, 256, size=(4, 9, 4), dtype=np.uint8)
    for pixels in (rgb, rgba):
        data = encode_png(pixels)
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert np.array_equal(decode_png(data), pixels)
    with pytest.raises(ValueError):
        encode_png(np.zeros((2, 2), dtype=np.uint8))

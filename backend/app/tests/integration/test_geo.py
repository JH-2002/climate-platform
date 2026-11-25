"""Spec 008, Parte A — hidrografia, DEM, terreno por setor e bacia, perfil e camadas.

O DEM daqui é sintético (blocos de 0,001° gerados com rasterio), com um vale em V ao longo da
latitude -23,476 (onde passa o trecho do Rio Tietê da fixture) e subida de 2 m a cada 0,001°
de latitude. A validação com o Copernicus real é feita no navegador (T128).
"""

from __future__ import annotations

import asyncio
import itertools
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.v1.deps import get_clock
from app.core.config import Settings, get_settings
from app.ingestion.geo_jobs import (
    Download,
    make_basin_sync_job,
    make_dem_job,
    make_drainage_sync_job,
    make_reservoir_sync_job,
)
from app.ingestion.pipeline import run_ingestion
from app.integrations.copernicus.dem import tiles_for_bbox
from app.main import create_app
from app.models.tables import basins, dem_assets, drainage_segments, sector_terrain
from app.services.geo import DEM_CLIP_CODE, compute_terrain
from app.tests.fixtures import GEOSAMPA_BASINS, GEOSAMPA_DRAINAGE, GEOSAMPA_RESERVOIRS, load
from app.tests.integration.test_flood_sync import run, sessions
from app.tests.integration.test_risk_api import FIXED_NOW, query, seed_and_compute

rasterio = pytest.importorskip("rasterio")

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

URL = "http://wfs.test/geoserver/geoportal/wfs"
HYDRO = {
    "geoportal:bacia_hidrografica": GEOSAMPA_BASINS,
    "geoportal:drenagem": GEOSAMPA_DRAINAGE,
    "geoportal:reservatorio_amortecimento": GEOSAMPA_RESERVOIRS,
}
BBOX = (-46.83, -24.01, -46.36, -23.35)
VALLEY_LAT = -23.476
STEP = 0.001


def synthetic_elevation(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    grid: np.ndarray = (700 + 2000 * np.abs(lat - VALLEY_LAT) + 0 * lon).astype("float32")
    return grid


def write_tile(code: str, path: Path) -> int:
    """Bloco de 1° com o nome do Copernicus (canto sudoeste no código)."""
    lat_s = -int(code.split("_S")[1][:2])
    lon_w = -int(code.split("_W")[1][:3])
    n = round(1 / STEP)
    lons = lon_w + (np.arange(n) + 0.5) * STEP
    lats = (lat_s + 1) - (np.arange(n) + 0.5) * STEP
    grid = synthetic_elevation(lons[None, :], lats[:, None])
    path.parent.mkdir(parents=True, exist_ok=True)
    from rasterio.transform import from_origin

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=n,
        height=n,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(lon_w, lat_s + 1, STEP, STEP),
    ) as dst:
        dst.write(grid, 1)
    return path.stat().st_size


def fake_downloader(calls: list[str]) -> Any:
    async def download(url: str, dest: Path) -> Download:
        calls.append(url)
        code = dest.stem
        return Download(etag=f"etag-{code}", bytes=write_tile(code, dest))

    return download


async def hydro_fetcher(_url: str, params: dict[str, str] | None) -> Any:
    return load(HYDRO[(params or {})["typeNames"]])


def sync_hydro() -> None:
    for code, factory in (
        ("geosampa-basins", make_basin_sync_job),
        ("geosampa-drainage", make_drainage_sync_job),
        ("geosampa-reservoirs", make_reservoir_sync_job),
    ):
        job = factory(hydro_fetcher, URL)

        def go(s: Any, c: str = code, j: Any = job) -> Any:
            return run_ingestion(s, c, j)

        outcome = run(go)
        assert outcome.status == "SUCCESS", outcome.error


def ensure_dem(dem_dir: Path, calls: list[str]) -> Any:
    job = make_dem_job(
        fake_downloader(calls), "https://dem.test", str(dem_dir), BBOX, DEM_CLIP_CODE
    )
    return run(lambda s: run_ingestion(s, "copernicus-dem", job))


def terrain(settings: Settings) -> Any:
    async def go() -> Any:
        async with sessions() as factory, factory() as session:
            return await compute_terrain(session, settings, FIXED_NOW)

    return asyncio.run(go())


@pytest.fixture
def dem_settings(tmp_path: Path) -> Settings:
    return get_settings().model_copy(update={"dem_dir": str(tmp_path / "dem")})


@pytest.fixture
def ready(dem_settings: Settings) -> Settings:
    """Setores, risco, hidrografia, DEM e terreno calculados."""
    seed_and_compute()
    sync_hydro()
    assert ensure_dem(Path(dem_settings.dem_dir), []).status == "SUCCESS"
    terrain(dem_settings)
    return dem_settings


@pytest.fixture
def client(ready: Settings) -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW
    app.dependency_overrides[get_settings] = lambda: ready
    with TestClient(app) as test_client:
        yield test_client


def test_hydrography_sync() -> None:
    sync_hydro()
    assert query(select(func.count()).select_from(basins))[0][0] == 4
    rows = query(select(drainage_segments.c.source_code, drainage_segments.c.open_channel))
    assert len(rows) == 8 and sum(1 for _, open_ in rows if not open_) == 3


def test_ac120_dem_downloads_once_and_covers_region(dem_settings: Settings) -> None:
    calls: list[str] = []
    first = ensure_dem(Path(dem_settings.dem_dir), calls)
    assert first.status == "SUCCESS" and len(calls) == len(tiles_for_bbox(*BBOX)) == 2
    clip = Path(dem_settings.dem_dir) / DEM_CLIP_CODE
    with rasterio.open(clip) as src:
        west, south, east, north = src.bounds
        data = src.read(1)
    assert west <= BBOX[0] and south <= BBOX[1] and east >= BBOX[2] and north >= BBOX[3]
    assert np.isfinite(data).all()
    second = ensure_dem(Path(dem_settings.dem_dir), calls)
    assert second.status == "SUCCESS" and len(calls) == 2  # nada baixado de novo
    assets = query(select(dem_assets.c.kind, dem_assets.c.etag))
    assert sorted(k for k, _ in assets) == ["CLIP", "TILE", "TILE"]


def test_terrain_without_dem_still_links_basin_and_drainage(dem_settings: Settings) -> None:
    seed_and_compute()
    sync_hydro()
    summary = terrain(dem_settings)
    assert summary.with_dem is False and summary.sectors == 6 and summary.outside_basins == 0
    rows = query(select(sector_terrain.c.elev_median_m, sector_terrain.c.basin_id))
    assert all(e is None and b is not None for e, b in rows)


def test_ac121_ac123_sector_terrain(client: TestClient) -> None:
    areas = {a["code"]: a for a in client.get("/api/v1/risk/areas?limit=100").json()["items"]}
    valley = client.get(f"/api/v1/geo/sectors/{areas['HMP-01-03']['id']}/terrain").json()
    assert valley["relative_elev_m"] < 0  # fundo do vale sintético
    assert valley["basin_name"].startswith("Área de Contribuição Direta")
    assert valley["nearest_drainage"]["distance_m"] < 500
    assert "modelo de superfície" in valley["disclaimer"]
    other = client.get(f"/api/v1/geo/sectors/{areas['HCL-10-02']['id']}/terrain").json()
    assert other["basin_name"] == "Córrego Pirajuçara"
    assert other["nearest_drainage"]["name"] in {"Córrego Pirajuçara", None}
    # AC-123: todo setor ativo numa bacia (ou contado como fora)
    listing = client.get("/api/v1/geo/basins").json()
    assert sum(b["sectors"] for b in listing["items"]) + listing["sectors_outside_basins"] == 6
    assert listing["total_sectors"] == 6


def test_basin_list_and_detail(client: TestClient) -> None:
    listing = client.get("/api/v1/geo/basins?ordem=setores").json()
    first = listing["items"][0]
    assert first["name"].startswith("Área de Contribuição Direta") and first["sectors"] == 3
    assert first["sectors_by_grade"] == {"R4": 0, "R3": 1, "R2": 1, "R1": 1}
    assert first["elev_min_m"] is not None and first["elev_min_m"] <= first["elev_max_m"]
    aricanduva = next(b for b in listing["items"] if b["name"] == "Rio Aricanduva")
    assert aricanduva["reservoirs"] >= 1 and aricanduva["reservoir_volume_m3"] >= 1800
    detail = client.get(f"/api/v1/geo/basins/{aricanduva['id']}").json()
    assert [s["code"] for s in detail["sectors"]] == ["HAF-06-02"]
    assert detail["reservoirs"][0]["name"] == "Aricanduva V"  # o maior primeiro
    assert detail["drainage_km_open"] > 0
    assert client.get("/api/v1/geo/basins/999999").status_code == 404


def test_ac122_profile_across_the_valley(client: TestClient) -> None:
    lon = -46.4334
    body = client.get(f"/api/v1/geo/profile?pontos={lon},-23.49;{lon},-23.46").json()
    samples = body["samples"]
    lowest = min(samples, key=lambda s: s["elevation_m"])
    assert abs(lowest["latitude"] - VALLEY_LAT) < 0.001
    rio = [c for c in body["crossings"] if c["kind"] == "drainage"]
    assert rio and rio[0]["name"] == "Rio Tietê"
    assert abs(rio[0]["distance_m"] - lowest["distance_m"]) < 200
    assert body["gain_m"] > 0 and body["loss_m"] > 0
    assert max(b["distance_m"] - a["distance_m"] for a, b in itertools.pairwise(samples)) <= 30.01


@pytest.mark.parametrize(
    ("pontos", "message"),
    [
        ("-46.43,-23.49", "2 a 10 pontos"),
        ("-46.43,-23.49;-46.20,-23.49", "limite é 20 km"),
        ("abc", "Ponto inválido"),
    ],
)
def test_profile_limits(client: TestClient, pontos: str, message: str) -> None:
    response = client.get(f"/api/v1/geo/profile?pontos={pontos}")
    assert response.status_code == 422 and message in response.json()["detail"]


def test_point_terrain(client: TestClient) -> None:
    body = client.get(f"/api/v1/geo/elevation?lat={VALLEY_LAT}&lon=-46.4334").json()
    assert body["elevation_m"] == pytest.approx(700, abs=2)
    assert body["relative_elev_m"] < 0
    assert body["nearest_drainage"]["name"] == "Rio Tietê"


def test_without_dem_profile_returns_503(dem_settings: Settings) -> None:
    seed_and_compute()
    app = create_app(get_settings())
    app.dependency_overrides[get_settings] = lambda: dem_settings
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/geo/profile?pontos=-46.43,-23.49;-46.43,-23.46")
        assert response.status_code == 503 and "ainda não foi baixado" in response.json()["detail"]
        assert test_client.get("/api/v1/geo/dem").json()["available"] is False


def test_map_layers(client: TestClient) -> None:
    basin_layer = client.get("/api/v1/map/layers/basins").json()
    assert len(basin_layer["features"]) == 4
    bbox = "-46.83,-24.01,-46.36,-23.35"
    far = client.get(f"/api/v1/map/layers/drainage?bbox={bbox}&zoom=11").json()
    near = client.get(f"/api/v1/map/layers/drainage?bbox={bbox}&zoom=13").json()
    assert len(far["features"]) == 5 and len(near["features"]) == 8  # zoom baixo: só a céu aberto
    assert client.get("/api/v1/map/layers/drainage?bbox=-48,-25,-45,-22").status_code == 422
    reservoirs = client.get("/api/v1/map/layers/reservoirs").json()
    assert len(reservoirs["features"]) == 3
    assert reservoirs["features"][0]["geometry"]["type"] == "Point"


# --- Parte B: relevo 3D (blocos terrarium), bloco da bacia e relevo sombreado ---------------


def tile_for(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    import math

    x = int((lon + 180) / 360 * 2**zoom)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**zoom)
    return x, y


def test_terrain_tile_encodes_copernicus_elevation(client: TestClient) -> None:
    from app.geo.png import decode_png
    from app.geo.terrain import terrarium_decode, tile_centers

    zoom = 12
    x, y = tile_for(-46.4334, VALLEY_LAT, zoom)
    response = client.get(f"/api/v1/geo/terrain/{zoom}/{x}/{y}.png")
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert "max-age" in response.headers["cache-control"]
    heights = terrarium_decode(decode_png(response.content))
    _, lats = tile_centers(zoom, x, y)
    row = int(np.argmin(np.abs(lats[:, 0] - VALLEY_LAT)))
    assert heights[row].min() == pytest.approx(701, abs=2)  # fundo do vale sintético
    expected = 700 + 2000 * np.abs(lats[:, 0] - VALLEY_LAT)
    assert np.allclose(heights[:, 128], expected, atol=2.5)


def test_terrain_tile_limits(client: TestClient) -> None:
    assert client.get("/api/v1/geo/terrain/3/0/0.png").status_code == 404  # zoom baixo demais
    assert client.get("/api/v1/geo/terrain/12/99999/0.png").status_code == 404
    far = client.get("/api/v1/geo/terrain/8/0/0.png")  # longe da região: bloco plano
    assert far.status_code == 200


def test_basin_block_real_and_simulated(client: TestClient) -> None:
    listing = client.get("/api/v1/geo/basins?ordem=setores").json()
    basin_id = listing["items"][0]["id"]
    real = client.get(f"/api/v1/geo/basins/{basin_id}/block").json()
    assert real["source"] == "real" and real["banner"] is None
    assert sorted(s["code"] for s in real["sectors"]) == ["HMP-01-03", "HMP-07-01", "HMP-07-02"]
    assert {s["category"] for s in real["sectors"]} <= {"LOW", "UNKNOWN"}
    assert real["bounds"]["west"] < real["bounds"]["east"]

    run = client.post(
        "/api/v1/simulation/runs",
        json={"total_mm": 60, "duration_h": 1, "pattern": "CONSTANT", "antecedent_mm": 0},
    ).json()
    simulated = client.get(f"/api/v1/geo/basins/{basin_id}/block?simulacao={run['id']}").json()
    assert simulated["source"] == "simulação" and simulated["banner"].startswith("SIMULAÇÃO")
    by_code = {s["code"]: s["category"] for s in simulated["sectors"]}
    assert by_code["HMP-01-03"] == "CRITICAL"

    import uuid

    missing = client.get(f"/api/v1/geo/basins/{basin_id}/block?simulacao={uuid.uuid4()}")
    assert missing.status_code == 404
    assert client.get("/api/v1/geo/basins/999999/block").status_code == 404


def test_basin_relief_png(client: TestClient) -> None:
    from app.geo.png import decode_png

    basin_id = client.get("/api/v1/geo/basins?ordem=setores").json()["items"][0]["id"]
    response = client.get(f"/api/v1/geo/basins/{basin_id}/relief.png")
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    pixels = decode_png(response.content)
    assert pixels.ndim == 3 and max(pixels.shape[:2]) <= 900 and pixels.shape[2] == 3
    colors = {tuple(int(v) for v in p) for p in pixels.reshape(-1, 3)}
    assert (11, 92, 122) in colors  # contorno da bacia
    assert (46, 139, 87) in colors  # setores em "baixo" na estimativa real do teste


def test_relief_and_tiles_without_dem(dem_settings: Settings) -> None:
    seed_and_compute()
    app = create_app(get_settings())
    app.dependency_overrides[get_settings] = lambda: dem_settings
    with TestClient(app) as test_client:
        assert test_client.get("/api/v1/geo/terrain/12/1517/2323.png").status_code == 503

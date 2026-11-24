"""T121 — parse das camadas de hidrografia do GeoSampa com respostas reais gravadas."""

from __future__ import annotations

import pytest

from app.integrations.geosampa.hydro import parse_basins, parse_drainage, parse_reservoirs
from app.tests.fixtures import GEOSAMPA_BASINS, GEOSAMPA_DRAINAGE, GEOSAMPA_RESERVOIRS, load


def test_basins() -> None:
    parsed = parse_basins(load(GEOSAMPA_BASINS))
    assert parsed.rejected == []
    by_code = {b.source_code: b for b in parsed.items}
    assert set(by_code) == {"9", "96", "211", "252"}
    aricanduva = by_code["252"]
    assert (aricanduva.name, aricanduva.main_basin, aricanduva.area_km2) == (
        "Rio Aricanduva",
        "Rio Tietê",
        103.9,
    )
    assert aricanduva.original_code == "1.1.11" and aricanduva.coverage == "Parcial"
    assert aricanduva.geometry["type"] == "Polygon"


def test_drainage_types_and_names() -> None:
    parsed = parse_drainage(load(GEOSAMPA_DRAINAGE))
    assert parsed.rejected == [] and len(parsed.items) == 8
    by_code = {d.source_code: d for d in parsed.items}
    tiete = by_code["905"]
    assert (tiete.name, tiete.feature_kind, tiete.open_channel) == ("Rio Tietê", "RIO", True)
    assert tiete.course_type == "Trecho em estado natural"
    assert tiete.length_m == pytest.approx(1183.86, abs=0.01)
    hidden = by_code["5008"]
    assert hidden.name is None and hidden.open_channel is False  # canalizado subterrâneo
    assert by_code["15197"].open_channel is True  # canalizado a céu aberto
    assert by_code["7763"].name == "Córrego Pirajuçara"


def test_reservoirs() -> None:
    parsed = parse_reservoirs(load(GEOSAMPA_RESERVOIRS))
    assert parsed.rejected == []
    by_name = {r.name: r for r in parsed.items}
    big = by_name["Aricanduva V"]
    assert (big.volume_m3, big.kind, big.realtime_monitoring) == (
        167000.0,
        "reservatorio off line",
        True,
    )
    assert big.subprefecture == "ITAQUERA" and big.local_basin == "Aricanduva"
    assert by_name["Pte. Aricanduva (margem direita)"].manager == "Estado"


def test_rejects_features_without_geometry_or_code() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": "drenagem.1", "geometry": None, "properties": {}},
            {
                "type": "Feature",
                "id": "drenagem.2",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"cd_identificador": 2, "nm_tipo_curso_hidrografia": "x"},
            },
        ],
    }
    assert [code for code, _ in parse_drainage(payload).rejected] == ["drenagem.1", "drenagem.2"]

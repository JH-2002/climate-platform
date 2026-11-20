"""T051 — parse das camadas do GeoSampa com recortes reais gravados em 2026-11-19."""

from __future__ import annotations

from datetime import date

import pytest

from app.integrations.geosampa.wfs import (
    LAYER_OCC_ALAGAMENTO,
    LAYER_OCC_INUNDACAO,
    LAYER_SECTORS,
    build_params,
    clean_subprefecture,
    normalize_processes,
    parse_flood_extents,
    parse_occurrences,
    parse_sectors,
)
from app.tests.fixtures import (
    GEOSAMPA_FLOOD_EXTENT,
    GEOSAMPA_OCC_ALAGAMENTO,
    GEOSAMPA_OCC_INUNDACAO,
    GEOSAMPA_SECTORS,
    load,
)


def test_params_request_geojson_in_wgs84() -> None:
    params = build_params(LAYER_SECTORS)
    assert params["typeNames"] == "geoportal:risco_hidrologico"
    assert params["outputFormat"] == "application/json"
    assert params["srsName"] == "EPSG:4326"


def test_sectors_from_real_response() -> None:
    parsed = parse_sectors(load(GEOSAMPA_SECTORS))
    assert parsed.rejected == []
    by_code = {s.source_code: s for s in parsed.items}
    assert set(by_code) == {
        "HCL-10-02",
        "HMB-17-02",
        "HAF-06-02",
        "HMP-01-03",
        "HMP-07-02",
        "HMP-07-01",
    }
    sector = by_code["HMP-01-03"]
    assert sector.grade == 3
    assert sector.area_code == "HMP-01"
    assert sector.area_name == "FAVELA DA PAZ"
    assert sector.households == 85
    assert sector.subprefecture == "SAO MIGUEL PAULISTA"
    assert sector.processes == ("ENCHENTE", "INUNDACAO")
    assert sector.inspected_on == date(2024, 5, 8)
    assert sector.geometry["type"] == "Polygon"
    lon, lat = sector.geometry["coordinates"][0][0]
    assert -47 < lon < -46 and -24 < lat < -23  # [lon, lat]


def test_flood_extents_from_real_response() -> None:
    parsed = parse_flood_extents(load(GEOSAMPA_FLOOD_EXTENT))
    assert [(e.source_code, e.return_period_years) for e in parsed.items] == [
        ("31", 100),
        ("32", 100),
    ]


def test_occurrences_from_real_response() -> None:
    alag = parse_occurrences(load(GEOSAMPA_OCC_ALAGAMENTO), LAYER_OCC_ALAGAMENTO)
    inund = parse_occurrences(load(GEOSAMPA_OCC_INUNDACAO), LAYER_OCC_INUNDACAO)
    assert len(alag.items) == 14 and len(inund.items) == 2
    first = next(o for o in alag.items if o.source_code == "1458")
    assert first.occurrence_type == "ALAGAMENTO"
    assert first.occurred_on == date(2026, 4, 1)
    assert first.subprefecture == "VILA PRUDENTE"
    assert (first.longitude, first.latitude) == (-46.5368208, -23.60621642)
    assert {o.occurrence_type for o in inund.items} == {"INUNDACAO"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ENCHENTE/INUNDACAO/ALAGAMENTO\n", ("ALAGAMENTO", "ENCHENTE", "INUNDACAO")),
        ("ENCHENTE/INUNDAÇÃO/ALAGAMENTO", ("ALAGAMENTO", "ENCHENTE", "INUNDACAO")),
        ("ENCHENTE/INUDACAO/ALAGAMENTO", ("ALAGAMENTO", "ENCHENTE", "INUNDACAO")),
        ("ENXURRADA", ("ENXURRADA",)),
        ("", ()),
        (None, ()),
    ],
)
def test_process_variants_are_normalized(raw: str | None, expected: tuple[str, ...]) -> None:
    assert normalize_processes(raw) == expected


def test_subprefecture_prefix_is_removed() -> None:
    assert clean_subprefecture("VP - VILA PRUDENTE") == "VILA PRUDENTE"
    assert clean_subprefecture("São Miguel  Paulista") == "SAO MIGUEL PAULISTA"
    assert clean_subprefecture(None) is None


def test_invalid_features_are_rejected_not_guessed() -> None:
    payload = load(GEOSAMPA_SECTORS)
    payload["features"][0]["properties"]["tx_grau_risco_hidrologico"] = "R9"
    payload["features"][1]["geometry"] = {"type": "Point", "coordinates": [-46.6, -23.5]}
    parsed = parse_sectors(payload)
    assert len(parsed.items) == 4
    assert {reason for _, reason in parsed.rejected} == {
        "grau de risco inválido",
        "geometria ausente ou não poligonal",
    }


def test_non_feature_collection_fails() -> None:
    with pytest.raises(ValueError, match="FeatureCollection"):
        parse_sectors({"type": "ExceptionReport"})
    with pytest.raises(ValueError, match="desconhecida"):
        parse_occurrences(load(GEOSAMPA_OCC_ALAGAMENTO), "outra_camada")

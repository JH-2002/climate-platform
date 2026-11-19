"""T012 — parser da lista de estações do INMET com a resposta real gravada."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.geo import BoundingBox
from app.integrations.inmet.stations import parse_stations
from app.tests.fixtures import INMET_STATIONS_SP, load

SAO_PAULO = BoundingBox.parse("-46.83,-24.01,-46.36,-23.35")


def test_region_filter_keeps_only_capital_stations() -> None:
    result = parse_stations(load(INMET_STATIONS_SP), region=SAO_PAULO)
    codes = sorted(s.external_code for s in result.stations)
    assert codes == ["A701", "A771"]
    assert result.rejected == []


def test_fields_are_normalized() -> None:
    result = parse_stations(load(INMET_STATIONS_SP))
    mirante = next(s for s in result.stations if s.external_code == "A701")
    assert mirante.name == "SAO PAULO - MIRANTE"
    assert mirante.state == "SP"
    assert mirante.latitude == pytest.approx(-23.4962888)
    assert mirante.longitude == pytest.approx(-46.6200666)
    assert mirante.altitude_m == pytest.approx(785.64)
    assert mirante.status == "OPERATIONAL"
    assert mirante.started_at == datetime(2006, 7, 25, 0, 0, tzinfo=UTC)


def test_status_mapping_and_placeholder_altitude() -> None:
    by_code = {s.external_code: s for s in parse_stations(load(INMET_STATIONS_SP)).stations}
    assert by_code["A755"].status == "FAULT"  # "Pane" na fonte
    assert by_code["A755"].source_status == "Pane"
    assert by_code["A789"].altitude_m is None  # fonte usa "0" como valor provisório
    assert by_code["A765"].altitude_m == pytest.approx(5.0)  # Bertioga: altitude baixa real


def test_end_of_operation_marks_inactive() -> None:
    item = dict(load(INMET_STATIONS_SP)[0], DT_FIM_OPERACAO="2025-01-01T00:00:00.000-03:00")
    result = parse_stations([item])
    assert result.stations[0].status == "INACTIVE"


def test_invalid_items_are_rejected_with_reason() -> None:
    good = load(INMET_STATIONS_SP)[0]
    payload = [good, {"CD_ESTACAO": "X1", "VL_LATITUDE": "abc", "VL_LONGITUDE": "-46"}, "lixo"]
    result = parse_stations(payload)
    assert len(result.stations) == 1
    assert ("X1", "coordenadas ausentes ou inválidas") in result.rejected
    assert ("#2", "item não é um objeto") in result.rejected


def test_non_list_payload_is_an_error() -> None:
    with pytest.raises(ValueError, match="array"):
        parse_stations({"erro": "x"})

"""Spec 009 — mensagens CAP 1.2 (IDAP e INMET) com respostas reais gravadas."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise

import pytest

from app.core.geo import BoundingBox
from app.integrations.cap import (
    UnsafeXmlError,
    multipolygon,
    parse_cap,
    parse_datetime,
    parse_polygon,
    parse_references,
    touches_bbox,
)
from app.tests.fixtures import INMET_CAP_ALERT, INMET_CAP_CANCEL, load_bytes

REGION = BoundingBox(-46.83, -24.01, -46.36, -23.35)


def test_parses_inmet_alert_fields() -> None:
    alert = parse_cap(load_bytes(INMET_CAP_ALERT))
    assert alert.identifier == "urn:oid:2.49.0.0.76.0.2026.28763.1"
    assert (alert.msg_type, alert.status, alert.severity) == ("Alert", "Actual", "Severe")
    assert alert.event == "Chuvas Intensas"
    assert alert.sent == datetime(2026, 11, 24, 15, 34, 10, tzinfo=UTC)
    assert alert.onset == datetime(2026, 11, 26, 3, 0, tzinfo=UTC)
    assert alert.expires == datetime(2026, 11, 27, 2, 59, tzinfo=UTC)
    assert alert.instruction is not None and "199" in alert.instruction
    assert alert.parameters["ColorRisk"] == "#F96602"
    assert alert.references == ()


def test_polygon_is_converted_to_lon_lat_and_closed() -> None:
    alert = parse_cap(load_bytes(INMET_CAP_ALERT))
    (ring,) = alert.polygons
    assert ring[0] == (-45.461426, -24.036431)
    assert ring[0] == ring[-1]
    # pontos repetidos em sequência são removidos
    assert all(a != b for a, b in pairwise(ring))
    geometry = multipolygon(alert)
    assert geometry is not None and geometry["type"] == "MultiPolygon"
    assert touches_bbox(alert, REGION)


def test_cancel_references_previous_alert() -> None:
    alert = parse_cap(load_bytes(INMET_CAP_CANCEL))
    assert alert.msg_type == "Cancel"
    assert alert.references == ("urn:oid:2.49.0.0.76.0.2026.28758.1",)


@pytest.mark.parametrize(
    "payload",
    [
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><alert/>',
        b"<!doctype html><alert/>",
        b'<alert><!ENTITY x SYSTEM "file:///etc/passwd"></alert>',
    ],
)
def test_rejects_doctype_and_entities(payload: bytes) -> None:
    with pytest.raises(UnsafeXmlError):
        parse_cap(payload)


def test_rejects_non_cap_element() -> None:
    with pytest.raises(ValueError, match="não é um alerta CAP"):
        parse_cap(b"<alert><identifier>1</identifier></alert>")


def test_polygon_edge_cases() -> None:
    assert parse_polygon(None) is None
    assert parse_polygon("-23,-46 -23,-46 -23,-46") is None  # menos de 3 vértices distintos
    assert parse_polygon("-23,-46 x,y -24,-47") is None
    assert parse_polygon("-95,-46 -23,-47 -24,-46") is None  # latitude fora dos limites
    ring = parse_polygon("-23,-46 -23,-47 -24,-46")
    assert ring == ((-46.0, -23.0), (-47.0, -23.0), (-46.0, -24.0), (-46.0, -23.0))


def test_dates_and_references() -> None:
    assert parse_datetime("2026-11-24T13:29:01-03:00") == datetime(
        2026, 11, 24, 16, 29, 1, tzinfo=UTC
    )
    assert parse_datetime("2026-11-24T13:29:01") == datetime(2026, 11, 24, 13, 29, 1, tzinfo=UTC)
    assert parse_datetime("ontem") is None
    assert parse_references("a,id-1,2026 b,id-2,2026") == ("id-1", "id-2")
    assert parse_references(None) == ()

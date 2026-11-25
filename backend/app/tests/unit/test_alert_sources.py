"""Spec 009 — feed da IDAP, avisos do INMET e subprefeituras do GeoSampa (respostas gravadas)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.geo import BoundingBox
from app.integrations.cap import parse_cap
from app.integrations.geosampa.admin import parse_subprefectures
from app.integrations.idap.feed import MAX_FEED_BYTES, read_feed
from app.integrations.inmet.warnings import color, concerns_region, municipality_codes, parse_rss
from app.tests.fixtures import (
    GEOSAMPA_SUBPREFECTURES,
    IDAP_FEED,
    INMET_CAP_ALERT,
    INMET_CAP_STORM,
    INMET_RSS,
    load,
    load_bytes,
)

REGION = BoundingBox(-46.83, -24.01, -46.36, -23.35)
SAO_PAULO = "3550308"


def test_idap_keeps_only_alerts_near_the_region() -> None:
    feed = read_feed(load_bytes(IDAP_FEED), REGION, SAO_PAULO)
    assert feed.total == 4
    assert [a.alert.identifier for a in feed.alerts] == [
        "200371/2026",
        "200433/2026",
        "200436/2026",
    ]  # Sorocaba (200364) fica de fora
    first = feed.alerts[0]
    assert first.alert.sender_name == "Defesa Civil Estadual De São Paulo"
    assert first.alert.expires == datetime(2026, 11, 25, 2, 30, tzinfo=UTC)
    assert first.xml.startswith('<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">')
    assert "<identifier>200371/2026</identifier>" in first.xml


def test_idap_ibge_geocode_counts_even_without_polygon_overlap() -> None:
    """Alerta sintético (formato da IDAP) com geocódigo IBGE e polígono longe da região."""
    entry = load_bytes(IDAP_FEED).decode().split("<entry>")[1].split("</entry>")[0]
    entry = entry.replace(
        "</polygon>",
        "</polygon>\n<geocode><valueName>IBGE</valueName><value>3550308</value></geocode>",
    )
    feed = f'<feed xmlns="http://www.w3.org/2005/Atom"><entry>{entry}</entry></feed>'
    result = read_feed(feed.encode(), REGION, SAO_PAULO)
    assert [a.alert.identifier for a in result.alerts] == ["200364/2026"]


def test_idap_limits() -> None:
    with pytest.raises(ValueError, match="acima de"):
        read_feed(b" " * (MAX_FEED_BYTES + 1), REGION, SAO_PAULO)
    with pytest.raises(ValueError, match="sem nenhum alerta"):
        read_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"/>', REGION, SAO_PAULO)


def test_inmet_rss_items() -> None:
    items = parse_rss(load_bytes(INMET_RSS))
    assert [i.item_id for i in items] == ["56504", "56503", "56501", "56500"]
    assert items[1].link == "https://apiprevmet3.inmet.gov.br/avisos/rss/56503"
    assert items[0].published == datetime(2026, 11, 25, tzinfo=UTC)


def test_inmet_municipalities_and_color() -> None:
    alert = parse_cap(load_bytes(INMET_CAP_ALERT))
    assert SAO_PAULO in municipality_codes(alert)
    assert concerns_region(alert, SAO_PAULO, REGION)
    assert not concerns_region(alert, "4314902", REGION)  # Porto Alegre não está na lista
    assert color(alert) == "#F96602"
    storm = parse_cap(load_bytes(INMET_CAP_STORM))
    assert storm.severity == "Severe" and SAO_PAULO in municipality_codes(storm)


def test_rss_that_is_not_rss_fails() -> None:
    with pytest.raises(ValueError, match="não é um RSS"):
        parse_rss(b"<html><body/></html>")


def test_subprefectures() -> None:
    parsed = parse_subprefectures(load(GEOSAMPA_SUBPREFECTURES))
    assert [(s.name, s.region5, s.acronym) for s in parsed.items] == [
        ("LAPA", "Oeste", "LA"),
        ("SE", "Centro", "SE"),
        ("PINHEIROS", "Oeste", "PI"),
    ]
    assert parsed.rejected == []
    bad = {"type": "FeatureCollection", "features": [{"id": "x", "properties": {}}]}
    assert parse_subprefectures(bad).rejected == [
        ("x", "subprefeitura sem código, nome ou polígono")
    ]

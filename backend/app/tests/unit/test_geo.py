"""Bounding box e pontos usados na configuração da região."""

from __future__ import annotations

import pytest

from app.core.geo import BoundingBox, parse_points

SAO_PAULO = "-46.83,-24.01,-46.36,-23.35"


def test_bbox_parses_and_contains() -> None:
    box = BoundingBox.parse(SAO_PAULO)
    assert box.contains(-23.4962888, -46.6200666)  # A701 Mirante
    assert not box.contains(-23.52388888, -46.86944443)  # A755 Barueri, fora do município


@pytest.mark.parametrize(
    "value",
    ["", "1,2,3", "a,b,c,d", "-46.3,-24,-46.8,-23.3", "-200,-24,-46,-23", "0,0,0,0"],
)
def test_invalid_bbox_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        BoundingBox.parse(value)


def test_points_parse() -> None:
    assert parse_points("-23.55,-46.63; -23.7,-46.7") == [(-23.55, -46.63), (-23.7, -46.7)]


@pytest.mark.parametrize("value", ["", ";", "-23.5", "x,y", "-95,10"])
def test_invalid_points_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        parse_points(value)

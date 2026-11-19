"""T040 — GeoJSON (RFC 7946): [lon, lat], anel fechado, FeatureCollection."""

from __future__ import annotations

from itertools import pairwise

from app.core.geo import BoundingBox
from app.services.geojson import bbox_polygon, feature_collection, point_feature


def test_point_feature_uses_lon_lat_order() -> None:
    f = point_feature(-46.6200666, -23.4962888, {"code": "A701"}, fid=2)
    assert f["geometry"] == {"type": "Point", "coordinates": [-46.620067, -23.496289]}
    assert f["id"] == 2
    assert f["properties"]["code"] == "A701"


def test_bbox_polygon_ring_is_closed_and_counterclockwise() -> None:
    poly = bbox_polygon(BoundingBox.parse("-46.83,-24.01,-46.36,-23.35"))
    ring = poly["coordinates"][0]
    assert ring[0] == ring[-1]
    assert len(ring) == 5
    # Área com sinal positiva = anti-horário (exigido para anéis externos na RFC 7946).
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in pairwise(ring))
    assert area > 0


def test_feature_collection_carries_extras() -> None:
    fc = feature_collection([], attribution="Fonte: INMET")
    assert fc == {"type": "FeatureCollection", "features": [], "attribution": "Fonte: INMET"}

"""Construtores de GeoJSON (RFC 7946). Funções puras; coordenadas sempre [lon, lat]."""

from __future__ import annotations

from typing import Any

from app.core.geo import BoundingBox

Feature = dict[str, Any]


def point_feature(lon: float, lat: float, properties: dict[str, Any], fid: Any = None) -> Feature:
    feature: Feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
        "properties": properties,
    }
    if fid is not None:
        feature["id"] = fid
    return feature


def bbox_polygon(bbox: BoundingBox) -> dict[str, Any]:
    ring = [
        [bbox.lon_min, bbox.lat_min],
        [bbox.lon_max, bbox.lat_min],
        [bbox.lon_max, bbox.lat_max],
        [bbox.lon_min, bbox.lat_max],
        [bbox.lon_min, bbox.lat_min],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def polygon_feature(geometry: dict[str, Any], properties: dict[str, Any]) -> Feature:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def feature_collection(features: list[Feature], **extra: Any) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features, **extra}

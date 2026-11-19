"""Tipos geográficos simples e validação de coordenadas (WGS84). Funções puras."""

from __future__ import annotations

import math
from dataclasses import dataclass


def is_valid_coordinate(lat: float, lon: float) -> bool:
    return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


@dataclass(frozen=True)
class BoundingBox:
    lon_min: float
    lat_min: float
    lon_max: float
    lat_max: float

    @classmethod
    def parse(cls, value: str) -> BoundingBox:
        parts = [p.strip() for p in value.split(",")]
        if len(parts) != 4:
            raise ValueError("bbox deve ter 4 números: lon_min,lat_min,lon_max,lat_max")
        try:
            lon_min, lat_min, lon_max, lat_max = (float(p) for p in parts)
        except ValueError:
            raise ValueError("bbox contém valor não numérico") from None
        if not (is_valid_coordinate(lat_min, lon_min) and is_valid_coordinate(lat_max, lon_max)):
            raise ValueError("bbox fora dos limites de latitude/longitude")
        if lon_min >= lon_max or lat_min >= lat_max:
            raise ValueError("bbox com mínimo maior ou igual ao máximo")
        return cls(lon_min, lat_min, lon_max, lat_max)

    def contains(self, lat: float, lon: float) -> bool:
        return self.lat_min <= lat <= self.lat_max and self.lon_min <= lon <= self.lon_max


def parse_points(value: str) -> list[tuple[float, float]]:
    """Converte "lat,lon;lat,lon" em pares validados."""
    points: list[tuple[float, float]] = []
    for chunk in value.split(";"):
        if not chunk.strip():
            continue
        parts = [p.strip() for p in chunk.split(",")]
        if len(parts) != 2:
            raise ValueError(f"ponto inválido: {chunk!r} (use lat,lon)")
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            raise ValueError(f"ponto inválido: {chunk!r}") from None
        if not is_valid_coordinate(lat, lon):
            raise ValueError(f"ponto fora dos limites: {chunk!r}")
        points.append((lat, lon))
    if not points:
        raise ValueError("informe ao menos um ponto")
    return points

"""Nomes de região para pontos da grade (textos de insight). Função pura."""

from __future__ import annotations

import math

# Praça da Sé, marco zero da cidade.
CITY_CENTER = (-23.5505, -46.6333)
CENTER_RADIUS_KM = 7.0
DIRECTIONS = ("Leste", "Nordeste", "Norte", "Noroeste", "Oeste", "Sudoeste", "Sul", "Sudeste")


def region_label(lat: float, lon: float) -> str:
    """ "Centro" ou direção a partir da Sé com a distância: "Sul (~16 km do centro)"."""
    dy = (lat - CITY_CENTER[0]) * 111.2
    dx = (lon - CITY_CENTER[1]) * 111.2 * math.cos(math.radians(CITY_CENTER[0]))
    distance = math.hypot(dx, dy)
    if distance < CENTER_RADIUS_KM:
        return "Centro"
    angle = math.degrees(math.atan2(dy, dx)) % 360
    direction = DIRECTIONS[int(((angle + 22.5) % 360) // 45)]
    return f"{direction} (~{round(distance)} km do centro)"

"""Estado de um alerta oficial, calculado na leitura (spec 009, FR-143). Funções puras."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

OfficialStatus = Literal["UPCOMING", "ACTIVE", "EXPIRED", "CANCELLED", "SUPERSEDED"]

SEVERITY_RANK: dict[str, int] = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1}
SEVERITY_LABELS: dict[str, str] = {
    "Extreme": "Extrema",
    "Severe": "Severa",
    "Moderate": "Moderada",
    "Minor": "Menor",
    "Unknown": "Desconhecida",
}


def official_status(
    now: datetime,
    onset_at: datetime | None,
    expires_at: datetime | None,
    ended_reason: str | None,
) -> OfficialStatus:
    if ended_reason == "CANCELLED":
        return "CANCELLED"
    if ended_reason == "SUPERSEDED":
        return "SUPERSEDED"
    if expires_at is not None and expires_at <= now:
        return "EXPIRED"
    if onset_at is not None and onset_at > now:
        return "UPCOMING"
    return "ACTIVE"


def severity_label(severity: str | None) -> str:
    return SEVERITY_LABELS.get(severity or "Unknown", severity or "Desconhecida")


_LOWER_WORDS = {"DE", "DO", "DA", "DOS", "DAS", "E"}
_SPECIAL = {"SE": "Sé", "M BOI MIRIM": "M'Boi Mirim"}


def display_name(name: str) -> str:
    """ "CASA VERDE-CACHOEIRINHA" -> "Casa Verde-Cachoeirinha"; "SE" -> "Sé"."""
    if name in _SPECIAL:
        return _SPECIAL[name]
    words = []
    for i, word in enumerate(name.split()):
        parts = [p.capitalize() for p in word.split("-")]
        joined = "-".join(parts)
        words.append(joined.lower() if i > 0 and word in _LOWER_WORDS else joined)
    return " ".join(words)

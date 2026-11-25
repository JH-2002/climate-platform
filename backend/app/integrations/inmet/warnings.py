"""Avisos meteorológicos do INMET (Alert-AS): RSS + uma mensagem CAP por aviso (spec 009, FR-141).

Formato confirmado em 2026-11-24 (SOURCES.md §16): o RSS lista os avisos (cerca de 60), e o CAP
de cada um traz o polígono e o parâmetro `Municipios` ("São Paulo - SP (3550308), ...").
O INMET usa `Alert`, `Update` e `Cancel`. Funções puras.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from app.core.geo import BoundingBox
from app.integrations.cap import CapAlert, safe_fromstring, touches_bbox

RSS_URL = "https://apiprevmet3.inmet.gov.br/avisos/rss"
_CODE = re.compile(r"\((\d{7})\)")
_ITEM_ID = re.compile(r"/(\d+)/?$")

# Severidade CAP -> nome e cor oficiais do INMET (BR-142).
INMET_LEVELS: dict[str, tuple[str, str]] = {
    "Moderate": ("Perigo potencial", "amarelo"),
    "Severe": ("Perigo", "laranja"),
    "Extreme": ("Grande perigo", "vermelho"),
}


@dataclass(frozen=True)
class RssItem:
    item_id: str
    link: str
    title: str | None
    published: datetime | None


def _published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_rss(data: bytes) -> list[RssItem]:
    root = safe_fromstring(data)
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise ValueError("resposta do INMET não é um RSS")
    items: list[RssItem] = []
    for item in channel.findall("item"):
        link = (item.findtext("link") or item.findtext("guid") or "").strip()
        match = _ITEM_ID.search(link)
        if not match:
            continue
        items.append(
            RssItem(
                item_id=match.group(1),
                link=link,
                title=(item.findtext("title") or "").strip() or None,
                published=_published(item.findtext("pubDate")),
            )
        )
    return items


def municipality_codes(alert: CapAlert) -> frozenset[str]:
    return frozenset(_CODE.findall(alert.parameters.get("Municipios", "")))


def concerns_region(alert: CapAlert, ibge_code: str, region: BoundingBox) -> bool:
    """O aviso cita o município da região; sem lista de municípios, vale o polígono."""
    codes = municipality_codes(alert)
    if codes:
        return ibge_code in codes
    return touches_bbox(alert, region)


def color(alert: CapAlert) -> str | None:
    value = alert.parameters.get("ColorRisk", "").strip()
    return value if re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else None

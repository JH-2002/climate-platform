"""Feed nacional da IDAP (Defesa Civil), Atom com mensagens CAP 1.2 (spec 009, FR-140).

Formato confirmado em 2026-11-24 (SOURCES.md §15): ~16 MB, só as ~12 h anteriores, um polígono
por alerta. O `areaDesc` da Defesa Civil de SP traz o estado inteiro ("SÃO PAULO/SP"), então a
área vale pelo polígono ou pelo código IBGE, quando houver.

Leitura em fluxo: cada alerta é interpretado e descartado; só os que cruzam a região ficam
(NFR-141). Função pura sobre bytes, sem rede.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.core.geo import BoundingBox
from app.integrations.cap import (
    CAP_NS,
    CapAlert,
    element_xml,
    ensure_safe_xml,
    parse_cap_element,
    touches_bbox,
)

FEED_URL = "https://idapfile.mdr.gov.br/idap/api/rss/cap"
MAX_FEED_BYTES = 60 * 1024 * 1024
ATOM_NS = "http://www.w3.org/2005/Atom"
IBGE_GEOCODE = "IBGE"


@dataclass(frozen=True)
class FeedAlert:
    alert: CapAlert
    xml: str


@dataclass
class FeedResult:
    alerts: list[FeedAlert] = field(default_factory=list)
    total: int = 0
    rejected: list[tuple[str, str]] = field(default_factory=list)


def concerns_region(alert: CapAlert, region: BoundingBox, ibge_code: str) -> bool:
    return ibge_code in alert.geocode_values(IBGE_GEOCODE) or touches_bbox(alert, region)


def read_feed(data: bytes, region: BoundingBox, ibge_code: str) -> FeedResult:
    """Alertas do feed que podem atingir a região (filtro por retângulo ou código IBGE).

    A interseção exata com o limite do município é feita depois, no banco.
    """
    if len(data) > MAX_FEED_BYTES:
        raise ValueError(f"feed da IDAP acima de {MAX_FEED_BYTES // (1024 * 1024)} MB")
    ensure_safe_xml(data)
    result = FeedResult()
    alert_tag = f"{{{CAP_NS}}}alert"
    entry_tag = f"{{{ATOM_NS}}}entry"
    for _event, element in ET.iterparse(io.BytesIO(data), events=("end",)):  # noqa: S314
        if element.tag == alert_tag:
            result.total += 1
            try:
                alert = parse_cap_element(element)
            except ValueError as exc:
                result.rejected.append(("?", str(exc)))
                continue
            if alert.status != "Actual":
                continue
            if concerns_region(alert, region, ibge_code):
                result.alerts.append(FeedAlert(alert, element_xml(element)))
        elif element.tag == entry_tag:
            element.clear()
    if result.total == 0:
        raise ValueError("feed da IDAP sem nenhum alerta CAP")
    return result

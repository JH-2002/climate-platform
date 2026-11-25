"""Mensagens CAP 1.2 (Common Alerting Protocol), usadas pela IDAP e pelo INMET (spec 009).

Funções puras: interpretam o XML e não decidem nada sobre risco (Constituição §10).
O XML chega de fontes externas: DOCTYPE e ENTITY são recusados antes de qualquer parse, o que
fecha a expansão de entidades e as referências externas sem biblioteca nova (ADR-014).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.geo import BoundingBox

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
_NS = {"cap": CAP_NS}
_UNSAFE = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)

ET.register_namespace("", CAP_NS)


class UnsafeXmlError(ValueError):
    """XML com DOCTYPE ou ENTITY: recusado sem parse."""


def ensure_safe_xml(data: bytes) -> None:
    if _UNSAFE.search(data):
        raise UnsafeXmlError("XML recusado: DOCTYPE ou ENTITY não são aceitos")


def safe_fromstring(data: bytes) -> ET.Element:
    ensure_safe_xml(data)
    return ET.fromstring(data)  # noqa: S314 — DOCTYPE/ENTITY recusados acima


Ring = tuple[tuple[float, float], ...]  # (lon, lat)


@dataclass(frozen=True)
class CapArea:
    description: str | None
    polygons: tuple[Ring, ...] = ()
    geocodes: tuple[tuple[str, str], ...] = ()  # (valueName, value), ex.: ("IBGE", "3550308")


@dataclass(frozen=True)
class CapAlert:
    identifier: str
    sender: str | None
    sent: datetime
    status: str
    msg_type: str
    references: tuple[str, ...]
    event: str | None
    categories: tuple[str, ...]
    severity: str | None
    urgency: str | None
    certainty: str | None
    onset: datetime | None
    expires: datetime | None
    sender_name: str | None
    headline: str | None
    description: str | None
    instruction: str | None
    web: str | None
    parameters: dict[str, str] = field(default_factory=dict)
    areas: tuple[CapArea, ...] = ()

    @property
    def polygons(self) -> tuple[Ring, ...]:
        return tuple(p for area in self.areas for p in area.polygons)

    def geocode_values(self, name: str) -> frozenset[str]:
        return frozenset(v for area in self.areas for k, v in area.geocodes if k == name)

    @property
    def area_description(self) -> str | None:
        parts = [a.description for a in self.areas if a.description]
        return "; ".join(parts) or None


def _text(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    found = el.find(path, _NS)
    if found is None or found.text is None:
        return None
    value = " ".join(found.text.split())
    return value or None


def parse_datetime(value: str | None) -> datetime | None:
    """ "2026-11-24T13:29:01-03:00" -> datetime em UTC. Sem fuso, assume UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_polygon(text: str | None) -> Ring | None:
    """Polígono CAP ("lat,lon lat,lon ...") -> anel fechado em (lon, lat).

    Pontos repetidos em sequência são removidos. Menos de 3 vértices distintos ou coordenada
    fora dos limites: devolve None.
    """
    if not text:
        return None
    points: list[tuple[float, float]] = []
    for pair in text.split():
        parts = pair.split(",")
        if len(parts) != 2:
            return None
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        if not points or points[-1] != (lon, lat):
            points.append((lon, lat))
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(set(points)) < 3:
        return None
    points.append(points[0])
    return tuple(points)


def parse_references(text: str | None) -> tuple[str, ...]:
    """ "sender,identifier,sent sender,identifier,sent" -> identificadores referenciados."""
    if not text:
        return ()
    ids: list[str] = []
    for triple in text.split():
        parts = triple.split(",")
        if len(parts) >= 2 and parts[1]:
            ids.append(parts[1])
    return tuple(ids)


def _areas(info: ET.Element) -> tuple[CapArea, ...]:
    areas: list[CapArea] = []
    for area in info.findall("cap:area", _NS):
        polygons = tuple(
            ring
            for poly in area.findall("cap:polygon", _NS)
            if (ring := parse_polygon(poly.text)) is not None
        )
        geocodes = tuple(
            (name, value)
            for code in area.findall("cap:geocode", _NS)
            if (name := _text(code, "cap:valueName")) and (value := _text(code, "cap:value"))
        )
        areas.append(CapArea(_text(area, "cap:areaDesc"), polygons, geocodes))
    return tuple(areas)


def _parameters(info: ET.Element) -> dict[str, str]:
    params: dict[str, str] = {}
    for param in info.findall("cap:parameter", _NS):
        name = _text(param, "cap:valueName")
        found = param.find("cap:value", _NS)
        if name and found is not None and found.text:
            params[name] = found.text.strip()
    return params


def parse_cap_element(alert: ET.Element) -> CapAlert:
    """Interpreta um `<alert>` CAP 1.2. Usa o primeiro `<info>` em português (ou o primeiro)."""
    if alert.tag != f"{{{CAP_NS}}}alert":
        raise ValueError("elemento não é um alerta CAP 1.2")
    identifier = _text(alert, "cap:identifier")
    sent = parse_datetime(_text(alert, "cap:sent"))
    if identifier is None or sent is None:
        raise ValueError("alerta CAP sem identificador ou data de envio")
    infos = alert.findall("cap:info", _NS)
    info = next(
        (i for i in infos if (_text(i, "cap:language") or "").lower().startswith("pt")),
        infos[0] if infos else None,
    )
    if info is None:
        raise ValueError(f"{identifier}: alerta CAP sem <info>")
    return CapAlert(
        identifier=identifier,
        sender=_text(alert, "cap:sender"),
        sent=sent,
        status=_text(alert, "cap:status") or "Actual",
        msg_type=_text(alert, "cap:msgType") or "Alert",
        references=parse_references(_text(alert, "cap:references")),
        event=_text(info, "cap:event"),
        categories=tuple(
            c.text.strip() for c in info.findall("cap:category", _NS) if c.text and c.text.strip()
        ),
        severity=_text(info, "cap:severity"),
        urgency=_text(info, "cap:urgency"),
        certainty=_text(info, "cap:certainty"),
        onset=parse_datetime(_text(info, "cap:onset"))
        or parse_datetime(_text(info, "cap:effective")),
        expires=parse_datetime(_text(info, "cap:expires")),
        sender_name=_text(info, "cap:senderName"),
        headline=_text(info, "cap:headline"),
        description=_text(info, "cap:description"),
        instruction=_text(info, "cap:instruction"),
        web=_text(info, "cap:web"),
        parameters=_parameters(info),
        areas=_areas(info),
    )


def parse_cap(data: bytes) -> CapAlert:
    return parse_cap_element(safe_fromstring(data))


def element_xml(alert: ET.Element) -> str:
    """XML do alerta como texto, para guardar o original em `raw_payloads`."""
    return ET.tostring(alert, encoding="unicode")


def ring_bbox(ring: Ring) -> BoundingBox:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return BoundingBox(min(lons), min(lats), max(lons), max(lats))


def bboxes_overlap(a: BoundingBox, b: BoundingBox) -> bool:
    return not (
        a.lon_max < b.lon_min
        or a.lon_min > b.lon_max
        or a.lat_max < b.lat_min
        or a.lat_min > b.lat_max
    )


def touches_bbox(alert: CapAlert, region: BoundingBox) -> bool:
    """Algum polígono do alerta tem retângulo que cruza o da região (filtro rápido, NFR-141)."""
    return any(bboxes_overlap(ring_bbox(ring), region) for ring in alert.polygons)


def multipolygon(alert: CapAlert) -> dict[str, Any] | None:
    """GeoJSON MultiPolygon com os polígonos do alerta (sem buracos, como no CAP)."""
    rings = alert.polygons
    if not rings:
        return None
    return {
        "type": "MultiPolygon",
        "coordinates": [[[list(p) for p in ring]] for ring in rings],
    }

"""Camadas do GeoSampa via WFS (spec 005, FR-060). Funções puras: parâmetros e parse.

Formato confirmado em 2026-11-19 (SOURCES.md §10): GeoJSON com `srsName=EPSG:4326`,
coordenadas [lon, lat]. Nenhuma regra de risco aqui (Constituição §10).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

DEFAULT_WFS_URL = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"

LAYER_SECTORS = "risco_hidrologico"
LAYER_FLOOD_EXTENT = "area_inundavel"
LAYER_OCC_ALAGAMENTO = "risco_ocorrencia_alagamento"
LAYER_OCC_INUNDACAO = "risco_ocorrencia_inundacao"

# Tipo de ocorrência gravado para cada camada.
OCCURRENCE_LAYERS: dict[str, str] = {
    LAYER_OCC_ALAGAMENTO: "ALAGAMENTO",
    LAYER_OCC_INUNDACAO: "INUNDACAO",
}

KNOWN_PROCESSES = ("ALAGAMENTO", "ENCHENTE", "ENXURRADA", "INUNDACAO")
# Grafias encontradas na camada (ex.: "INUDACAO", com acento, com quebra de linha).
_PROCESS_ALIASES = {"INUDACAO": "INUNDACAO"}
_POLYGON_TYPES = ("Polygon", "MultiPolygon")
_GRADE = re.compile(r"^R([1-4])$")
_SECTOR_SUFFIX = re.compile(r"\s*\(R[1-4]\)\s*$")


@dataclass(frozen=True)
class RiskSector:
    source_code: str
    area_code: str | None
    area_name: str | None
    grade: int
    processes: tuple[str, ...]
    households: int | None
    subprefecture: str | None
    basin: str | None
    inspected_on: date | None
    geometry: dict[str, Any]


@dataclass(frozen=True)
class FloodExtent:
    source_code: str
    return_period_years: int
    geometry: dict[str, Any]


@dataclass(frozen=True)
class FloodOccurrence:
    source_code: str
    occurrence_type: str
    occurred_on: date
    subprefecture: str | None
    longitude: float
    latitude: float


@dataclass
class ParseResult[T]:
    items: list[T] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)


def build_params(layer: str) -> dict[str, str]:
    return {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"geoportal:{layer}",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }


def _ascii_upper(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def normalize_processes(raw: str | None) -> tuple[str, ...]:
    """ "ENCHENTE/INUNDAÇÃO/ALAGAMENTO\\n" -> ("ALAGAMENTO", "ENCHENTE", "INUNDACAO")."""
    if not raw:
        return ()
    found: set[str] = set()
    for part in re.split(r"[/,;]", _ascii_upper(raw)):
        name = part.strip()
        name = _PROCESS_ALIASES.get(name, name)
        if name in KNOWN_PROCESSES:
            found.add(name)
    return tuple(sorted(found))


def clean_subprefecture(raw: Any) -> str | None:
    """ "VP - VILA PRUDENTE" -> "VILA PRUDENTE"; "PINHEIROS" -> "PINHEIROS"."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if " - " in text:
        text = text.split(" - ", 1)[1]
    return " ".join(_ascii_upper(text).split())


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _date(value: Any) -> date | None:
    """ "2026-04-01Z" -> date(2026, 4, 1)."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _features(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ValueError("resposta não é uma FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection sem lista de feições")
    return [f for f in features if isinstance(f, dict)]


def _feature_id(feature: dict[str, Any]) -> str:
    return str(feature.get("id") or "?")


def _polygon(feature: dict[str, Any]) -> dict[str, Any] | None:
    geometry = feature.get("geometry")
    if (
        isinstance(geometry, dict)
        and geometry.get("type") in _POLYGON_TYPES
        and geometry.get("coordinates")
    ):
        return geometry
    return None


def parse_sectors(payload: Any) -> ParseResult[RiskSector]:
    result: ParseResult[RiskSector] = ParseResult()
    for feature in _features(payload):
        fid = _feature_id(feature)
        props = feature.get("properties") or {}
        raw_code = _text(props.get("sg_setor_risco_hidrologico"))
        if raw_code is None:
            result.rejected.append((fid, "setor sem código"))
            continue
        code = _SECTOR_SUFFIX.sub("", raw_code)
        grade_match = _GRADE.match(_text(props.get("tx_grau_risco_hidrologico")) or "")
        if grade_match is None:
            result.rejected.append((code, "grau de risco inválido"))
            continue
        geometry = _polygon(feature)
        if geometry is None:
            result.rejected.append((code, "geometria ausente ou não poligonal"))
            continue
        households = props.get("qt_moradia")
        result.items.append(
            RiskSector(
                source_code=code,
                area_code=_text(props.get("sg_area_risco_hidrologico")),
                area_name=_text(props.get("nm_area_risco_hidrologico")),
                grade=int(grade_match.group(1)),
                processes=normalize_processes(props.get("tx_tipo_processo")),
                households=int(households) if isinstance(households, int | float) else None,
                subprefecture=clean_subprefecture(props.get("nm_subprefeitura")),
                basin=_text(props.get("nm_bacia_hidrografica")),
                inspected_on=_date(props.get("dt_vistoria")),
                geometry=geometry,
            )
        )
    return result


def parse_flood_extents(payload: Any) -> ParseResult[FloodExtent]:
    result: ParseResult[FloodExtent] = ParseResult()
    for feature in _features(payload):
        fid = _feature_id(feature)
        props = feature.get("properties") or {}
        code = props.get("cd_identificador_area_inundavel")
        period = props.get("qt_tempo_retorno")
        geometry = _polygon(feature)
        if code is None or not isinstance(period, int | float) or geometry is None:
            result.rejected.append((fid, "mancha sem código, período de retorno ou geometria"))
            continue
        result.items.append(FloodExtent(str(code), int(period), geometry))
    return result


def parse_occurrences(payload: Any, layer: str) -> ParseResult[FloodOccurrence]:
    if layer not in OCCURRENCE_LAYERS:
        raise ValueError(f"camada de ocorrências desconhecida: {layer}")
    occurrence_type = OCCURRENCE_LAYERS[layer]
    result: ParseResult[FloodOccurrence] = ParseResult()
    for feature in _features(payload):
        fid = _feature_id(feature)
        props = feature.get("properties") or {}
        code = _text(str(props.get("cd_identificador") or ""))
        occurred_on = _date(props.get("dt_ocorrencia"))
        geometry = feature.get("geometry")
        coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if (
            code is None
            or occurred_on is None
            or not isinstance(geometry, dict)
            or geometry.get("type") != "Point"
            or not isinstance(coords, list)
            or len(coords) < 2
        ):
            result.rejected.append((fid, "ocorrência sem código, data ou ponto"))
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            result.rejected.append((code, "coordenada fora dos limites"))
            continue
        result.items.append(
            FloodOccurrence(
                source_code=code,
                occurrence_type=occurrence_type,
                occurred_on=occurred_on,
                subprefecture=clean_subprefecture(props.get("nm_subprefeitura")),
                longitude=lon,
                latitude=lat,
            )
        )
    return result

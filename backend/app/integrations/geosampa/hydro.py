"""Hidrografia do GeoSampa via WFS (spec 008, FR-121): bacias, drenagem e piscinões.

Formato confirmado em 2026-11-20 (SOURCES.md §13): GeoJSON com `srsName=EPSG:4326`.
Funções puras: só interpretam a resposta, sem regra de negócio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.integrations.geosampa.wfs import (
    ParseResult,
    _feature_id,
    _features,
    _polygon,
    _text,
    clean_subprefecture,
)

LAYER_BASINS = "bacia_hidrografica"
LAYER_DRAINAGE = "drenagem"
LAYER_RESERVOIRS = "reservatorio_amortecimento"

_LINE_TYPES = ("LineString", "MultiLineString")
# Tipos de trecho a céu aberto (o resto é fechado/subterrâneo ou lago).
_OPEN_TYPES = ("Trecho em estado natural", "Trecho canalizado a céu aberto")


@dataclass(frozen=True)
class Basin:
    source_code: str
    original_code: str | None
    name: str
    main_basin: str | None
    area_km2: float | None
    coverage: str | None
    geometry: dict[str, Any]


@dataclass(frozen=True)
class DrainageSegment:
    source_code: str
    name: str | None
    feature_kind: str | None
    course_type: str
    open_channel: bool
    length_m: float | None
    geometry: dict[str, Any]


@dataclass(frozen=True)
class DetentionReservoir:
    source_code: str
    reservoir_code: str | None
    name: str
    local_basin: str | None
    main_basin: str | None
    stream: str | None
    volume_m3: float | None
    kind: str | None
    emptying: str | None
    manager: str | None
    realtime_monitoring: bool | None
    subprefecture: str | None
    built: str | None
    geometry: dict[str, Any]


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _code(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    return _text(str(value))


def parse_basins(payload: Any) -> ParseResult[Basin]:
    result: ParseResult[Basin] = ParseResult()
    for feature in _features(payload):
        fid = _feature_id(feature)
        props = feature.get("properties") or {}
        code = _code(props.get("cd_identificador_bacia_hidrografica"))
        name = _text(props.get("nm_bacia_hidrografica"))
        geometry = _polygon(feature)
        if code is None or name is None or geometry is None:
            result.rejected.append((fid, "bacia sem código, nome ou polígono"))
            continue
        result.items.append(
            Basin(
                source_code=code,
                original_code=_text(props.get("cd_identificador_original_bacia_hidrografica")),
                name=name,
                main_basin=_text(props.get("nm_bacia_hidrografica_principal")),
                area_km2=_number(props.get("qt_area_quilometro")),
                coverage=_text(props.get("tx_abrangencia")),
                geometry=geometry,
            )
        )
    return result


def _line(feature: dict[str, Any]) -> dict[str, Any] | None:
    geometry = feature.get("geometry")
    if (
        isinstance(geometry, dict)
        and geometry.get("type") in _LINE_TYPES
        and geometry.get("coordinates")
    ):
        return geometry
    return None


def drainage_name(props: dict[str, Any]) -> str | None:
    """Nome legível ("Rio Tietê"); cai para o nome em maiúsculas da fonte."""
    return _text(props.get("nm_descritivo")) or _text(props.get("nm_acidente"))


def parse_drainage(payload: Any) -> ParseResult[DrainageSegment]:
    result: ParseResult[DrainageSegment] = ParseResult()
    for feature in _features(payload):
        fid = _feature_id(feature)
        props = feature.get("properties") or {}
        code = _code(props.get("cd_identificador"))
        course = _text(props.get("nm_tipo_curso_hidrografia"))
        geometry = _line(feature)
        if code is None or course is None or geometry is None:
            result.rejected.append((fid, "trecho sem código, tipo ou linha"))
            continue
        kind = _text(props.get("tx_tipo_acidente"))
        result.items.append(
            DrainageSegment(
                source_code=code,
                name=drainage_name(props),
                feature_kind=kind,
                course_type=course,
                open_channel=course in _OPEN_TYPES,
                length_m=_number(props.get("qt_comprimento_hidrografia")),
                geometry=geometry,
            )
        )
    return result


def _yes(value: Any) -> bool | None:
    text = _text(value)
    if text is None:
        return None
    return text.lower() in ("sim", "s", "yes")


def parse_reservoirs(payload: Any) -> ParseResult[DetentionReservoir]:
    result: ParseResult[DetentionReservoir] = ParseResult()
    for feature in _features(payload):
        fid = _feature_id(feature)
        props = feature.get("properties") or {}
        code = _code(props.get("cd_identificador_reservatorio_amortecimento"))
        name = _text(props.get("nm_reservatorio"))
        geometry = _polygon(feature)
        if code is None or name is None or geometry is None:
            result.rejected.append((fid, "piscinão sem código, nome ou polígono"))
            continue
        result.items.append(
            DetentionReservoir(
                source_code=code,
                reservoir_code=_text(props.get("cd_reservatorio")),
                name=name,
                local_basin=_text(props.get("nm_bacia_hidrografica_local")),
                main_basin=_text(props.get("nm_bacia_hidrografica_principal")),
                stream=_text(props.get("nm_corrego")),
                volume_m3=_number(props.get("qt_volume_metro")),
                kind=_text(props.get("tx_tipo_reservatorio")),
                emptying=_text(props.get("tx_tipo_esvaziamento")),
                manager=_text(props.get("tx_gestao")),
                realtime_monitoring=_yes(props.get("tx_monitoramento_tempo_real")),
                subprefecture=clean_subprefecture(props.get("nm_subprefeitura")),
                built=_text(props.get("an_construcao")),
                geometry=geometry,
            )
        )
    return result

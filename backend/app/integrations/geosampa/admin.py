"""Subprefeituras do GeoSampa via WFS (spec 009, FR-142): limite do município e regiões.

Formato confirmado em 2026-11-24 (SOURCES.md §17): 32 polígonos, com `nm_regiao_05`
(Norte, Sul, Leste, Oeste, Centro). Funções puras.
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

LAYER_SUBPREFECTURES = "subprefeitura"


@dataclass(frozen=True)
class Subprefecture:
    source_code: str
    name: str
    acronym: str | None
    region5: str | None
    geometry: dict[str, Any]


def parse_subprefectures(payload: Any) -> ParseResult[Subprefecture]:
    result: ParseResult[Subprefecture] = ParseResult()
    for feature in _features(payload):
        fid = _feature_id(feature)
        props = feature.get("properties") or {}
        code = _text(str(props.get("cd_subprefeitura") or ""))
        name = clean_subprefecture(props.get("nm_subprefeitura"))
        geometry = _polygon(feature)
        if code is None or name is None or geometry is None:
            result.rejected.append((fid, "subprefeitura sem código, nome ou polígono"))
            continue
        result.items.append(
            Subprefecture(
                source_code=code,
                name=name,
                acronym=_text(props.get("sg_subprefeitura")),
                region5=_text(props.get("nm_regiao_05")),
                geometry=geometry,
            )
        )
    return result

"""Lista de estações automáticas do INMET (`GET /estacoes/T`, sem token).

Formato confirmado no smoke test de 2026-11-19 (ver docs/data-sources/smoke-results.md).
Funções puras: não fazem I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.geo import BoundingBox, is_valid_coordinate

STATIONS_URL = "https://apitempo.inmet.gov.br/estacoes/T"

_STATUS_MAP = {"Operante": "OPERATIONAL", "Pane": "FAULT"}


@dataclass(frozen=True)
class StationRecord:
    external_code: str
    name: str
    state: str | None
    latitude: float
    longitude: float
    altitude_m: float | None
    status: str
    source_status: str | None
    started_at: datetime | None
    ended_at: datetime | None


@dataclass(frozen=True)
class StationParseResult:
    stations: list[StationRecord]
    rejected: list[tuple[str, str]]  # (código ou posição, motivo)


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def map_status(source_status: str | None, ended_at: datetime | None) -> str:
    if ended_at is not None:
        return "INACTIVE"
    if source_status is None:
        return "UNKNOWN"
    return _STATUS_MAP.get(source_status.strip(), "UNKNOWN")


def parse_station(item: dict[str, Any]) -> StationRecord:
    code = str(item.get("CD_ESTACAO") or "").strip()
    if not code:
        raise ValueError("estação sem código (CD_ESTACAO)")
    lat = _parse_float(item.get("VL_LATITUDE"))
    lon = _parse_float(item.get("VL_LONGITUDE"))
    if lat is None or lon is None or not is_valid_coordinate(lat, lon):
        raise ValueError("coordenadas ausentes ou inválidas")
    altitude = _parse_float(item.get("VL_ALTITUDE"))
    ended_at = _parse_datetime(item.get("DT_FIM_OPERACAO"))
    source_status = item.get("CD_SITUACAO")
    return StationRecord(
        external_code=code,
        name=str(item.get("DC_NOME") or code).strip(),
        state=(str(item["SG_ESTADO"]).strip() if item.get("SG_ESTADO") else None),
        latitude=lat,
        longitude=lon,
        # A fonte usa "0" como valor provisório em estações sem altitude cadastrada.
        altitude_m=altitude if altitude not in (None, 0.0) else None,
        status=map_status(source_status, ended_at),
        source_status=source_status,
        started_at=_parse_datetime(item.get("DT_INICIO_OPERACAO")),
        ended_at=ended_at,
    )


def parse_stations(payload: Any, region: BoundingBox | None = None) -> StationParseResult:
    """Valida a lista e, se `region` for informada, mantém só as estações dentro dela."""
    if not isinstance(payload, list):
        raise ValueError("resposta inesperada: a lista de estações deve ser um array JSON")
    stations: list[StationRecord] = []
    rejected: list[tuple[str, str]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            rejected.append((f"#{index}", "item não é um objeto"))
            continue
        try:
            record = parse_station(item)
        except ValueError as exc:
            rejected.append((str(item.get("CD_ESTACAO") or f"#{index}"), str(exc)))
            continue
        if region is None or region.contains(record.latitude, record.longitude):
            stations.append(record)
    return StationParseResult(stations=stations, rejected=rejected)

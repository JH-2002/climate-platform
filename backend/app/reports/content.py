"""Conteúdo neutro de um relatório (spec 010): o mesmo `Report` vira PDF, CSV ou JSON.

Módulo puro. Os montadores (`services/reports.py`) preenchem o `Report` com os serviços que a
tela já usa (BR-150); os escritores só traduzem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

DataKind = Literal["OBSERVED", "FORECAST", "MODELED", "DERIVED", "SIMULATED", "OFFICIAL_TEXT"]
KIND_LABELS: dict[str, str] = {
    "OBSERVED": "medido (observação)",
    "FORECAST": "previsão de modelo",
    "MODELED": "modelo (reanálise)",
    "DERIVED": "calculado pelo sistema",
    "SIMULATED": "simulado (cenário hipotético)",
    "OFFICIAL_TEXT": "texto oficial da fonte",
}

ColumnType = Literal["text", "number", "int", "datetime", "date"]


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    type: ColumnType = "text"
    digits: int = 1
    unit: str | None = None
    width: float = 1.0  # peso relativo da largura no PDF

    @property
    def header(self) -> str:
        return f"{self.label} ({self.unit})" if self.unit else self.label


@dataclass(frozen=True)
class Heading:
    text: str


@dataclass(frozen=True)
class Paragraph:
    text: str
    style: Literal["normal", "note", "warning"] = "normal"


@dataclass(frozen=True)
class Figures:
    """Números de destaque: (rótulo, valor já formatado)."""

    items: tuple[tuple[str, str], ...]
    source: str | None = None


@dataclass(frozen=True)
class Table:
    key: str
    title: str
    columns: tuple[Column, ...]
    rows: tuple[dict[str, Any], ...]
    source: str
    data_kind: DataKind | None = None
    note: str | None = None
    main: bool = False
    empty_text: str = "Nenhum registro."


@dataclass(frozen=True)
class BarChart:
    title: str
    labels: tuple[str, ...]
    values: tuple[float, ...]
    unit: str
    source: str
    data_kind: DataKind | None = None


Block = Heading | Paragraph | Figures | Table | BarChart


@dataclass(frozen=True)
class Report:
    report_type: str
    title: str
    generated_at: datetime
    params: dict[str, Any]
    blocks: tuple[Block, ...]
    warnings: tuple[str, ...] = ()
    attributions: tuple[str, ...] = ()
    mode: Literal["REAL", "SIMULATION"] = "REAL"
    banner: str | None = None
    subtitle: str | None = None
    versions: dict[str, str] = field(default_factory=dict)

    @property
    def tables(self) -> list[Table]:
        return [b for b in self.blocks if isinstance(b, Table)]

    def main_table(self) -> Table | None:
        tables = self.tables
        return next((t for t in tables if t.main), tables[0] if tables else None)


def local_datetime(value: datetime) -> datetime:
    return value.astimezone(LOCAL_TZ)


def format_number(value: float, digits: int = 1) -> str:
    """1234.5 -> "1.234,5" (português)."""
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_value(value: Any, column: Column) -> str:
    """Valor de célula para leitura humana (PDF). Ausente vira "—"."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if column.type == "number" and isinstance(value, int | float):
        return format_number(float(value), column.digits)
    if column.type == "int" and isinstance(value, int | float):
        return format_number(float(value), 0)
    if column.type == "datetime" and isinstance(value, datetime):
        return local_datetime(value).strftime("%d/%m/%Y %H:%M")
    if column.type == "date" and isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, list | tuple):
        return ", ".join(str(v) for v in value)
    return str(value)


def generated_text(report: Report) -> str:
    return local_datetime(report.generated_at).strftime("%d/%m/%Y %H:%M") + " (Brasília)"

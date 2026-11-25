"""CSV e JSON de um relatório (spec 010). Funções puras.

CSV (NFR-154): UTF-8 com BOM, `;`, vírgula decimal, para abrir direto no Excel em português;
linhas `#` no topo com fonte, tipo, horário e avisos; células que começam com `=`, `+`, `-`
ou `@` ganham `'` na frente (injeção de fórmula).
JSON: todo o conteúdo, com `metadata`.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from app.reports.content import (
    KIND_LABELS,
    BarChart,
    Column,
    Figures,
    Heading,
    Paragraph,
    Report,
    Table,
    generated_text,
    local_datetime,
)

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value: Any, column: Column) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sim" if value else "não"
    if column.type in ("number", "int") and isinstance(value, int | float):
        digits = 0 if column.type == "int" else column.digits
        return f"{value:.{digits}f}".replace(".", ",")
    if isinstance(value, datetime):
        return local_datetime(value).strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list | tuple):
        value = ", ".join(str(v) for v in value)
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_START) else text


def render_csv(report: Report) -> bytes:
    table = report.main_table()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    comments: list[str] = []
    if report.banner:
        comments.append(report.banner)
    comments.append(f"Relatório: {report.title}")
    comments.append(f"Gerado em: {generated_text(report)}")
    if table is not None:
        comments.append(f"Tabela: {table.title}")
        comments.append(f"Fonte: {table.source}")
        if table.data_kind:
            comments.append(f"Tipo do dado: {KIND_LABELS[table.data_kind]}")
    comments.extend(f"Aviso: {w}" for w in report.warnings)
    comments.append("Horários em Brasília; decimal com vírgula.")
    for line in comments:
        buffer.write(f"# {line}\r\n")
    if table is not None:
        writer.writerow([col.header for col in table.columns])
        for row in table.rows:
            writer.writerow([csv_cell(row.get(col.key), col) for col in table.columns])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"tipo não serializável: {type(value).__name__}")


def _block(block: Any) -> dict[str, Any]:
    if isinstance(block, Table):
        return {
            "type": "table",
            "key": block.key,
            "title": block.title,
            "source": block.source,
            "data_kind": block.data_kind,
            "note": block.note,
            "columns": [asdict(c) for c in block.columns],
            "rows": list(block.rows),
        }
    if isinstance(block, BarChart):
        return {"type": "bar_chart", **asdict(block)}
    if isinstance(block, Figures):
        return {
            "type": "figures",
            "items": [{"label": label, "value": value} for label, value in block.items],
            "source": block.source,
        }
    if isinstance(block, Heading):
        return {"type": "heading", "text": block.text}
    if isinstance(block, Paragraph):
        return {"type": "paragraph", "text": block.text, "style": block.style}
    raise TypeError(f"bloco desconhecido: {type(block).__name__}")


def render_json(report: Report) -> bytes:
    document = {
        "metadata": {
            "report_type": report.report_type,
            "title": report.title,
            "generated_at": report.generated_at.isoformat(),
            "mode": report.mode,
            "banner": report.banner,
            "params": report.params,
            "warnings": list(report.warnings),
            "attributions": list(report.attributions),
            "versions": report.versions,
            "time_zone_note": "Horários em UTC (ISO 8601); a tela e o PDF mostram Brasília.",
        },
        "sections": [_block(b) for b in report.blocks],
    }
    return json.dumps(document, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")

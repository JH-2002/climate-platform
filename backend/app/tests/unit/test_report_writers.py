"""Spec 010 — escritores de PDF, CSV e JSON (puros)."""

from __future__ import annotations

import json
import re
import zlib
from datetime import UTC, date, datetime

from app.reports.content import (
    BarChart,
    Column,
    Figures,
    Heading,
    Paragraph,
    Report,
    Table,
    format_number,
    format_value,
)
from app.reports.pdf import render_pdf, text_width, wrap
from app.reports.writers import csv_cell, render_csv, render_json

NOW = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)  # 23h de 24/11 em Brasília

COLUMNS = (
    Column("code", "Setor"),
    Column("name", "Área", width=2),
    Column("p24", "Chuva 24 h", "number", unit="mm"),
    Column("when", "Atualizado", "datetime"),
)


def report(rows: int = 3, banner: str | None = None) -> Report:
    data = tuple(
        {
            "code": f"HMP-{i:02d}",
            "name": '=HYPERLINK("x")' if i == 0 else "Jardim São Luís — várzea do córrego",
            "p24": i * 1.25,
            "when": NOW,
        }
        for i in range(rows)
    )
    return Report(
        report_type="risco",
        title="Risco por setor — São Paulo",
        generated_at=NOW,
        params={"subprefecture": None},
        blocks=(
            Heading("Resumo"),
            Figures((("Em alto", "5"), ("Chuva máxima", "36,1 mm"))),
            Paragraph("Ação, coração e São Paulo."),
            BarChart("Chuva", ("Centro", "Leste"), (1.5, 3.0), "mm", "Open-Meteo", "FORECAST"),
            Table("setores", "Setores", COLUMNS, data, "GeoSampa", "DERIVED", main=True),
        ),
        warnings=("Estimativa experimental, não é alerta oficial.",),
        attributions=("Previsão: Open-Meteo.com (CC BY 4.0)",),
        banner=banner,
        mode="SIMULATION" if banner else "REAL",
    )


def _streams(pdf: bytes) -> list[str]:
    raw = re.findall(rb"stream\n(.*?)\nendstream", pdf, re.S)
    return [zlib.decompress(s).decode("ascii") for s in raw]


def test_pdf_structure_and_xref() -> None:
    pdf = render_pdf(report())
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    startxref = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
    assert pdf[startxref : startxref + 4] == b"xref"
    # cada entrada da xref aponta para o início de um objeto
    entries = pdf[startxref:].split(b"\n")[3:]
    for number, line in enumerate(entries, start=1):
        if not line.endswith(b" n "):
            break
        offset = int(line[:10])
        assert pdf[offset:].startswith(f"{number} 0 obj".encode())
    assert b"/BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding" in pdf


def test_pdf_text_is_winansi_with_footer_on_every_page() -> None:
    pdf = render_pdf(report(rows=150))
    pages = _streams(pdf)
    assert len(pages) >= 3
    # "ç" = 0xE7 = \347 em octal; "ã" = 0xE3 = \343
    assert "cora\\347\\343o" in pages[0]
    for number, stream in enumerate(pages, start=1):
        assert f"P\\341gina {number} de {len(pages)}" in stream
        assert "Estimativa experimental" in stream
        assert "Setor" in stream or number == 1  # cabeçalho da tabela repetido
    assert b"/Count " + str(len(pages)).encode() in pdf


def test_pdf_banner_on_every_page() -> None:
    banner = "SIMULAÇÃO — CENÁRIO HIPOTÉTICO, NÃO É PREVISÃO NEM ALERTA"
    pages = _streams(render_pdf(report(rows=150, banner=banner)))
    assert all("SIMULA\\307\\303O" in p for p in pages)


def test_wrap_and_widths() -> None:
    assert text_width("a", 10) == 5.56  # largura AFM da Helvetica: 556/1000 em
    assert text_width("a", 10, bold=True) == 5.56
    lines = wrap("palavra " * 30, 100, 10)
    assert len(lines) > 1 and all(text_width(line, 10) <= 100 for line in lines)
    assert all(text_width(line, 10) <= 50 for line in wrap("x" * 80, 50, 10))
    assert wrap("", 100, 10) == [""]


def test_values_in_portuguese() -> None:
    assert format_number(1234.5) == "1.234,5"
    assert format_value(None, COLUMNS[2]) == "—"
    assert format_value(1.5, COLUMNS[2]) == "1,5"
    assert format_value(NOW, COLUMNS[3]) == "24/11/2026 23:00"
    assert format_value(date(2026, 1, 5), Column("d", "D", "date")) == "05/01/2026"
    assert format_value(True, COLUMNS[0]) == "sim"


def test_csv_for_excel_with_comments_and_formula_escape() -> None:
    raw = render_csv(report(banner="SIMULAÇÃO — CENÁRIO HIPOTÉTICO"))
    assert raw.startswith("﻿".encode())
    text = raw.decode("utf-8-sig")
    lines = text.split("\r\n")
    assert lines[0] == "# SIMULAÇÃO — CENÁRIO HIPOTÉTICO"
    assert "# Fonte: GeoSampa" in lines
    assert "# Tipo do dado: calculado pelo sistema" in lines
    header = next(line for line in lines if not line.startswith("#"))
    assert header == "Setor;Área;Chuva 24 h (mm);Atualizado"
    assert "HMP-01;Jardim São Luís — várzea do córrego;1,2;2026-11-24 23:00" in lines
    assert lines[lines.index(header) + 1].startswith("HMP-00;\"'=HYPERLINK")
    assert csv_cell("-1", COLUMNS[0]) == "'-1"
    assert csv_cell(-1.5, COLUMNS[2]) == "-1,5"  # número negativo continua número


def test_json_keeps_raw_values_and_metadata() -> None:
    doc = json.loads(render_json(report(banner="SIMULAÇÃO")))
    assert doc["metadata"]["mode"] == "SIMULATION"
    assert doc["metadata"]["generated_at"] == "2026-11-25T02:00:00+00:00"
    table = next(s for s in doc["sections"] if s["type"] == "table")
    assert table["rows"][1]["p24"] == 1.25
    assert table["columns"][2]["unit"] == "mm"
    assert [s["type"] for s in doc["sections"]][:3] == ["heading", "figures", "paragraph"]

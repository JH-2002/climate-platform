"""Escritor de PDF próprio (spec 010, NFR-150; ADR-015). Puro: só a biblioteca padrão.

PDF 1.4, A4, fontes padrão Helvetica e Helvetica-Bold em WinAnsi (cp1252, cobre os acentos do
português), larguras das métricas AFM da Adobe (`afm.py`). Faz texto com quebra de linha,
números de destaque, tabelas paginadas (cabeçalho repetido), gráfico de barras e, em todas as
páginas, a faixa de simulação (quando houver) e o rodapé com avisos e numeração.
"""

from __future__ import annotations

import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.reports.afm import FIRST_CHAR, HELVETICA, HELVETICA_BOLD
from app.reports.content import (
    KIND_LABELS,
    BarChart,
    Column,
    Figures,
    Heading,
    Paragraph,
    Report,
    Table,
    format_number,
    format_value,
    generated_text,
)

PAGE_W, PAGE_H = 595.28, 841.89
MARGIN = 42.0
CONTENT_W = PAGE_W - 2 * MARGIN
FOOTER_H = 46.0
BANNER_H = 22.0
INK = (0.08, 0.13, 0.17)
MUTED = (0.30, 0.36, 0.42)
ACCENT = (0.04, 0.36, 0.48)
WARN = (0.54, 0.35, 0.0)
SIM = (0.43, 0.16, 0.85)
GRID = (0.80, 0.84, 0.87)
STRIPE = (0.96, 0.97, 0.98)


def encode(text: str) -> bytes:
    """Texto -> bytes WinAnsi; o que não existe no cp1252 vira "?"."""
    return text.encode("cp1252", errors="replace")


def text_width(text: str, size: float, bold: bool = False) -> float:
    widths = HELVETICA_BOLD if bold else HELVETICA
    total = 0
    for byte in encode(text):
        index = byte - FIRST_CHAR
        total += widths[index] if 0 <= index < len(widths) and widths[index] else 556
    return total * size / 1000.0


def wrap(text: str, width: float, size: float, bold: bool = False) -> list[str]:
    """Quebra por palavras; palavra maior que a linha é cortada."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}" if current else word
            if text_width(candidate, size, bold) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while text_width(word, size, bold) > width and len(word) > 1:
                cut = len(word)
                while cut > 1 and text_width(word[:cut], size, bold) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines or [""]


def _escape(data: bytes) -> str:
    out = []
    for byte in data:
        ch = chr(byte)
        if ch in "\\()":
            out.append("\\" + ch)
        elif 32 <= byte < 127:
            out.append(ch)
        else:
            out.append(f"\\{byte:03o}")
    return "".join(out)


def _rgb(color: tuple[float, float, float]) -> str:
    return " ".join(f"{c:.3f}" for c in color)


@dataclass
class _Page:
    ops: list[str] = field(default_factory=list)


class _Canvas:
    """Páginas e cursor vertical. Coordenadas do PDF: origem embaixo à esquerda."""

    def __init__(self, report: Report) -> None:
        self.report = report
        self.pages: list[_Page] = []
        self.y = 0.0
        self.new_page()

    @property
    def top(self) -> float:
        return PAGE_H - MARGIN - (BANNER_H + 6 if self.report.banner else 0)

    @property
    def bottom(self) -> float:
        return MARGIN + FOOTER_H

    def new_page(self) -> None:
        self.pages.append(_Page())
        self.y = self.top
        if len(self.pages) > 1:
            self.text(MARGIN, self.y - 9, self.report.title, 8, color=MUTED)
            self.y -= 18

    def ensure(self, height: float) -> None:
        if self.y - height < self.bottom:
            self.new_page()

    @property
    def ops(self) -> list[str]:
        return self.pages[-1].ops

    def text(
        self,
        x: float,
        y: float,
        text: str,
        size: float,
        bold: bool = False,
        color: tuple[float, float, float] = INK,
        page: _Page | None = None,
    ) -> None:
        font = "F2" if bold else "F1"
        target = (page or self.pages[-1]).ops
        body = _escape(encode(text))
        target.append(
            f"BT /{font} {size:.1f} Tf {_rgb(color)} rg {x:.2f} {y:.2f} Td ({body}) Tj ET"
        )

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: tuple[float, float, float],
        page: _Page | None = None,
    ) -> None:
        (page or self.pages[-1]).ops.append(f"{_rgb(fill)} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def line(
        self, x1: float, y1: float, x2: float, y2: float, color: tuple[float, float, float] = GRID
    ) -> None:
        self.ops.append(f"{_rgb(color)} RG 0.5 w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def paragraph(
        self,
        text: str,
        size: float = 9.5,
        bold: bool = False,
        color: tuple[float, float, float] = INK,
        gap: float = 6,
    ) -> None:
        leading = size * 1.35
        for line in wrap(text, CONTENT_W, size, bold):
            self.ensure(leading)
            self.y -= leading
            self.text(MARGIN, self.y + size * 0.25, line, size, bold, color)
        self.y -= gap


def _heading(c: _Canvas, block: Heading) -> None:
    c.ensure(40)
    c.y -= 8
    c.paragraph(block.text, 12.5, bold=True, color=ACCENT, gap=4)


def _figures(c: _Canvas, block: Figures) -> None:
    per_row = 3
    gap = 8.0
    box_w = (CONTENT_W - gap * (per_row - 1)) / per_row
    box_h = 46.0
    for start in range(0, len(block.items), per_row):
        c.ensure(box_h + gap)
        top = c.y
        for i, (label, value) in enumerate(block.items[start : start + per_row]):
            x = MARGIN + i * (box_w + gap)
            c.rect(x, top - box_h, box_w, box_h, STRIPE)
            c.text(x + 8, top - 15, wrap(label, box_w - 16, 7.5)[0], 7.5, color=MUTED)
            c.text(x + 8, top - 36, wrap(value, box_w - 16, 15, True)[0], 15, bold=True)
        c.y = top - box_h - gap
    if block.source:
        c.paragraph(block.source, 7.5, color=MUTED, gap=6)


def _column_widths(columns: Sequence[Column]) -> list[float]:
    total = sum(col.width for col in columns) or 1.0
    return [CONTENT_W * col.width / total for col in columns]


def _table_header(c: _Canvas, table: Table, widths: list[float], size: float) -> None:
    lines = [
        wrap(col.header, w - 6, size, True) for col, w in zip(table.columns, widths, strict=True)
    ]
    height = max(len(cell) for cell in lines) * size * 1.25 + 6
    c.ensure(height + size * 2)
    c.rect(MARGIN, c.y - height, CONTENT_W, height, (0.89, 0.92, 0.94))
    x = MARGIN
    for cell, w in zip(lines, widths, strict=True):
        for i, text in enumerate(cell):
            c.text(x + 3, c.y - 3 - size - i * size * 1.25 + 1, text, size, bold=True)
        x += w
    c.y -= height


def _table(c: _Canvas, table: Table) -> None:
    c.ensure(60)
    c.y -= 4
    c.paragraph(table.title, 10.5, bold=True, gap=2)
    kind = f" · Tipo: {KIND_LABELS[table.data_kind]}" if table.data_kind else ""
    c.paragraph(f"Fonte: {table.source}{kind}", 7.5, color=MUTED, gap=4)
    if not table.rows:
        c.paragraph(table.empty_text, 9, color=MUTED)
        return
    size = 7.5 if len(table.columns) > 5 else 8.5
    widths = _column_widths(table.columns)
    _table_header(c, table, widths, size)
    leading = size * 1.25
    for index, row in enumerate(table.rows):
        cells = [
            wrap(format_value(row.get(col.key), col), w - 6, size)
            for col, w in zip(table.columns, widths, strict=True)
        ]
        height = max(len(cell) for cell in cells) * leading + 5
        if c.y - height < c.bottom:
            c.new_page()
            _table_header(c, table, widths, size)
        if index % 2 == 1:
            c.rect(MARGIN, c.y - height, CONTENT_W, height, STRIPE)
        x = MARGIN
        for col, cell, w in zip(table.columns, cells, widths, strict=True):
            numeric = col.type in ("number", "int")
            for i, text in enumerate(cell):
                tx = x + w - 3 - text_width(text, size) if numeric else x + 3
                c.text(tx, c.y - 3 - size - i * leading + 1, text, size)
            x += w
        c.y -= height
        c.line(MARGIN, c.y, MARGIN + CONTENT_W, c.y)
    c.y -= 4
    if table.note:
        c.paragraph(table.note, 7.5, color=MUTED, gap=6)
    else:
        c.y -= 6


def _bars(c: _Canvas, chart: BarChart) -> None:
    items = list(zip(chart.labels, chart.values, strict=True))[:24]
    if not items:
        return
    bar_h, gap = 11.0, 4.0
    c.ensure(40 + min(len(items), 6) * (bar_h + gap))
    c.y -= 4
    c.paragraph(chart.title, 10.5, bold=True, gap=2)
    kind = f" · Tipo: {KIND_LABELS[chart.data_kind]}" if chart.data_kind else ""
    c.paragraph(f"Fonte: {chart.source}{kind}", 7.5, color=MUTED, gap=4)
    label_w = min(170.0, max(text_width(label, 8) for label, _ in items) + 8)
    value_w = 70.0
    bar_area = CONTENT_W - label_w - value_w
    peak = max((v for _, v in items), default=0.0) or 1.0
    for label, value in items:
        c.ensure(bar_h + gap)
        c.y -= bar_h + gap
        c.text(MARGIN, c.y + 2.5, wrap(label, label_w - 6, 8)[0], 8)
        length = max(0.0, bar_area * value / peak)
        c.rect(MARGIN + label_w, c.y, length, bar_h, ACCENT)
        c.text(
            MARGIN + label_w + length + 4, c.y + 2.5, f"{format_number(value, 1)} {chart.unit}", 8
        )
    c.y -= 10


def _decorate(c: _Canvas) -> None:
    """Faixa de simulação no topo e rodapé em todas as páginas (FR-153, FR-154)."""
    report = c.report
    total = len(c.pages)
    footer_lines = wrap(" · ".join(report.warnings), CONTENT_W, 6.5) if report.warnings else []
    attribution = " · ".join(report.attributions)
    for number, page in enumerate(c.pages, start=1):
        if report.banner:
            y = PAGE_H - MARGIN - BANNER_H
            c.rect(MARGIN, y, CONTENT_W, BANNER_H, SIM, page=page)
            c.text(
                MARGIN + 8,
                y + 7,
                wrap(report.banner, CONTENT_W - 16, 9, True)[0],
                9,
                True,
                (1, 1, 1),
                page,
            )
        y = MARGIN + FOOTER_H - 10
        rule_y = y + 6
        right = MARGIN + CONTENT_W
        page.ops.append(
            f"{_rgb(GRID)} RG 0.5 w {MARGIN:.2f} {rule_y:.2f} m {right:.2f} {rule_y:.2f} l S"
        )
        for line in footer_lines[:2]:
            c.text(MARGIN, y - 2, line, 6.5, color=WARN, page=page)
            y -= 8.5
        if attribution:
            c.text(
                MARGIN,
                y - 2,
                wrap(attribution, CONTENT_W - 90, 6.5)[0],
                6.5,
                color=MUTED,
                page=page,
            )
        label = f"Página {number} de {total}"
        c.text(
            MARGIN + CONTENT_W - text_width(label, 7),
            MARGIN - 4,
            label,
            7,
            color=MUTED,
            page=page,
        )
        c.text(MARGIN, MARGIN - 4, f"Gerado em {generated_text(report)}", 7, color=MUTED, page=page)


def _pdf_string(text: str) -> str:
    """Texto do dicionário Info em UTF-16BE (aceita qualquer caractere)."""
    return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


def _serialize(pages: list[_Page], title: str) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # preenchido depois
    pages_id = add(b"")
    font_regular = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    font_bold = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    producer = "(Plataforma de Inteligencia Climatica)"
    info = add(f"<< /Title {_pdf_string(title)} /Producer {producer} >>".encode())
    resources = f"<< /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >>"
    kids: list[int] = []
    for page in pages:
        stream = zlib.compress("\n".join(page.ops).encode("ascii"))
        content = add(
            f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )
        kids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_W:.2f} {PAGE_H:.2f}] "
                f"/Resources {resources} /Contents {content} 0 R >>".encode()
            )
        )
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    refs = " ".join(f"{k} 0 R" for k in kids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{refs}] /Count {len(kids)} >>".encode()

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def render_pdf(report: Report) -> bytes:
    c = _Canvas(report)
    c.paragraph(report.title, 17, bold=True, gap=2)
    if report.subtitle:
        c.paragraph(report.subtitle, 9.5, color=MUTED, gap=2)
    c.paragraph(f"Gerado em {generated_text(report)}", 8.5, color=MUTED, gap=8)
    for warning in report.warnings:
        c.paragraph(warning, 8.5, bold=True, color=WARN, gap=3)
    c.y -= 4
    for block in report.blocks:
        if isinstance(block, Heading):
            _heading(c, block)
        elif isinstance(block, Paragraph):
            color = {"normal": INK, "note": MUTED, "warning": WARN}[block.style]
            c.paragraph(block.text, 9 if block.style != "normal" else 9.5, color=color)
        elif isinstance(block, Figures):
            _figures(c, block)
        elif isinstance(block, Table):
            _table(c, block)
        elif isinstance(block, BarChart):
            _bars(c, block)
    if report.attributions:
        _heading(c, Heading("Fontes e atribuições"))
        for attribution in report.attributions:
            c.paragraph(attribution, 8.5, color=MUTED, gap=2)
    _decorate(c)
    return _serialize(c.pages, report.title)

"""Tabela de chuva mensal do IAG/USP (spec 006, FR-080). Funções puras.

A Prefeitura publica a série em PDF (SOURCES.md §11). O texto extraído do PDF traz números no
formato brasileiro ("1.238,5") e, às vezes, espaços dentro deles ("17 0,8"), herdados do
espaçamento das letras. Como todo valor tem exatamente uma casa decimal, os espaços podem ser
removidos e os números relidos sem ambiguidade.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
FIRST_YEAR = 1933
SUM_TOLERANCE_MM = 0.15  # arredondamento a uma casa em 12 valores

_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})*,\d")
_YEAR_LINE = re.compile(r"^\s*(\d{4})\s+(.*)$")
_NORMAL_LINE = re.compile(r"^\s*Normal\S*\s*\\?\((\d{4}-\d{4})\\?\)\s*(.*)$")


@dataclass(frozen=True)
class MonthlyYear:
    year: int
    months: tuple[float, ...]  # 12 valores, mm
    annual: float

    @property
    def months_sum(self) -> float:
        return round(sum(self.months), 1)


@dataclass(frozen=True)
class PublishedNormal:
    period: str  # "1991-2020"
    months: tuple[float, ...]
    annual: float


@dataclass
class ParsedTable:
    years: list[MonthlyYear] = field(default_factory=list)
    normals: list[PublishedNormal] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)


def parse_number(text: str) -> float:
    """ "1.238,5" -> 1238.5."""
    return float(text.replace(".", "").replace(",", "."))


def numbers_in(text: str) -> list[float]:
    return [parse_number(n) for n in _NUMBER.findall(re.sub(r"\s+", "", text))]


def parse_table_text(lines: Iterable[str], last_year: int) -> ParsedTable:
    """Linhas de texto do PDF -> anos e normais. Linhas sem 13 valores são rejeitadas."""
    table = ParsedTable()
    for line in lines:
        normal = _NORMAL_LINE.match(line)
        if normal:
            values = numbers_in(normal.group(2))
            if len(values) == 13:
                table.normals.append(
                    PublishedNormal(normal.group(1), tuple(values[:12]), values[12])
                )
            else:
                table.rejected.append((normal.group(1), f"{len(values)} valores"))
            continue
        row = _YEAR_LINE.match(line)
        if not row or not FIRST_YEAR <= int(row.group(1)) <= last_year:
            continue
        values = numbers_in(row.group(2))
        if len(values) != 13:
            table.rejected.append((row.group(1), f"{len(values)} valores"))
            continue
        table.years.append(MonthlyYear(int(row.group(1)), tuple(values[:12]), values[12]))
    return table


def validate(years: list[MonthlyYear], last_year: int) -> list[str]:
    """Problemas encontrados (vazio = série íntegra)."""
    problems: list[str] = []
    found = {y.year for y in years}
    missing = [y for y in range(FIRST_YEAR, last_year + 1) if y not in found]
    if missing:
        problems.append(f"anos ausentes: {missing}")
    if len(found) != len(years):
        problems.append("anos repetidos")
    for y in years:
        if any(v < 0 for v in y.months):
            problems.append(f"{y.year}: valor negativo")
        if abs(y.months_sum - y.annual) > SUM_TOLERANCE_MM:
            problems.append(f"{y.year}: soma dos meses {y.months_sum} ≠ total {y.annual}")
    return problems


def read_csv(path: Path) -> list[MonthlyYear]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            MonthlyYear(int(row["ano"]), tuple(float(row[m]) for m in MONTHS), float(row["anual"]))
            for row in csv.DictReader(handle)
        ]


def read_normals_csv(path: Path) -> list[PublishedNormal]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            PublishedNormal(
                row["periodo"], tuple(float(row[m]) for m in MONTHS), float(row["anual"])
            )
            for row in csv.DictReader(handle)
        ]


def write_csv(path: Path, years: list[MonthlyYear]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["ano", *MONTHS, "anual"])
        for y in sorted(years, key=lambda item: item.year):
            writer.writerow([y.year, *(f"{v:.1f}" for v in y.months), f"{y.annual:.1f}"])


def write_normals_csv(path: Path, normals: list[PublishedNormal]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["periodo", *MONTHS, "anual"])
        for n in normals:
            writer.writerow([n.period, *(f"{v:.1f}" for v in n.months), f"{n.annual:.1f}"])

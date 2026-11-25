"""Extrai a tabela de chuva mensal do IAG/USP do PDF da Prefeitura (spec 006, T070).

Uso (atualização anual, assistida):
    1. Baixe o PDF em https://prefeitura.sp.gov.br/documents/d/licenciamento/ (Precipitação
       pluviométrica 1933–AAAA) e salve localmente.
    2. python scripts/extract_iag_table.py caminho/do.pdf AAAA
    3. Confira a saída: o script falha se faltar ano ou se a soma dos meses não bater com o
       total anual. Atualize o JSON de metadados (URL, data, sha256) e faça o commit.

Requer `pdftotext` (poppler-utils). A leitura dos números fica em
`app/integrations/iag/monthly_table.py`, testada com casos reais de espaçamento do PDF.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.integrations.iag.monthly_table import (  # noqa: E402
    parse_table_text,
    validate,
    write_csv,
    write_normals_csv,
)

OUTPUT_DIR = ROOT / "backend" / "data" / "reference"


def pdf_text(pdf: Path) -> list[str]:
    if shutil.which("pdftotext") is None:
        raise SystemExit("pdftotext não encontrado (instale poppler-utils)")
    result = subprocess.run(  # noqa: S603 — executável fixo, argumento é um caminho local
        ["pdftotext", "-layout", str(pdf), "-"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("last_year", type=int)
    args = parser.parse_args(argv)

    table = parse_table_text(pdf_text(args.pdf), args.last_year)
    problems = validate(table.years, args.last_year)
    if table.rejected:
        problems.append(f"linhas rejeitadas: {table.rejected}")
    if problems:
        print("Tabela não conferida:", *problems, sep="\n- ", file=sys.stderr)
        return 1

    csv_path = OUTPUT_DIR / f"iag_usp_chuva_mensal_1933_{args.last_year}.csv"
    write_csv(csv_path, table.years)
    write_normals_csv(OUTPUT_DIR / "iag_usp_normais_publicadas.csv", table.normals)
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    print(f"{len(table.years)} anos conferidos → {csv_path.name}")
    print(f"sha256 do PDF: {digest} (registre no JSON de metadados)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

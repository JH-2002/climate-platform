"""Importação da chuva mensal medida do IAG/USP (spec 006, FR-080, AC-080).

Lê o CSV de referência versionado em `data/reference/` e as normais publicadas, confere a
série (anos completos e soma dos meses = total anual) e grava com proveniência.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert

from app.ingestion.pipeline import IngestionContext, Job, JobResult
from app.integrations.iag.monthly_table import read_csv, read_normals_csv, validate
from app.models.tables import published_normals, rain_monthly_observed

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"
IAG_CSV = "iag_usp_chuva_mensal_1933_2025.csv"
IAG_METADATA = "iag_usp_chuva_mensal_1933_2025.json"
IAG_NORMALS = "iag_usp_normais_publicadas.csv"
IAG_LAST_YEAR = 2025


def make_iag_import_job(directory: Path = REFERENCE_DIR) -> Job:
    async def job(ctx: IngestionContext) -> JobResult:
        csv_path = directory / IAG_CSV
        metadata: dict[str, Any] = json.loads((directory / IAG_METADATA).read_text("utf-8"))
        years = read_csv(csv_path)
        problems = validate(years, IAG_LAST_YEAR)
        if problems:
            raise ValueError("série do IAG não conferida: " + "; ".join(problems[:5]))
        file_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        await ctx.store_raw(
            {"metadata": metadata, "csv": IAG_CSV, "csv_sha256": file_hash},
            str(metadata["url"]),
        )
        station = str(metadata["estacao_codigo"])
        result = JobResult(received=len(years) * 12)
        rows = [
            {
                "source_id": ctx.source_id,
                "station_code": station,
                "year": y.year,
                "month": month,
                "value_mm": value,
                "kind": "OBSERVED",
                "source_file": IAG_CSV,
                "file_hash": file_hash,
                "imported_at": ctx.now,
            }
            for y in years
            for month, value in enumerate(y.months, start=1)
        ]
        for start in range(0, len(rows), 500):
            base = insert(rain_monthly_observed).values(rows[start : start + 500])
            stmt = base.on_conflict_do_update(
                index_elements=["source_id", "station_code", "year", "month"],
                set_={
                    "value_mm": base.excluded.value_mm,
                    "source_file": base.excluded.source_file,
                    "file_hash": base.excluded.file_hash,
                    "imported_at": base.excluded.imported_at,
                },
            ).returning(rain_monthly_observed.c.id, _xmax_zero())
            for _id, inserted in (await ctx.session.execute(stmt)).tuples():
                if inserted:
                    result.inserted += 1
                else:
                    result.updated += 1

        normals = read_normals_csv(directory / IAG_NORMALS)
        normal_rows = [
            {
                "source_id": ctx.source_id,
                "station_code": station,
                "period": n.period,
                "month": month,
                "value_mm": value,
            }
            for n in normals
            for month, value in [*enumerate(n.months, start=1), (0, n.annual)]
        ]
        if normal_rows:
            base = insert(published_normals).values(normal_rows)
            await ctx.session.execute(
                base.on_conflict_do_update(
                    index_elements=["source_id", "station_code", "period", "month"],
                    set_={"value_mm": base.excluded.value_mm},
                )
            )
        await ctx.session.commit()
        return result

    return job


def _xmax_zero() -> Any:
    return (literal_column("xmax") == 0).label("inserted")

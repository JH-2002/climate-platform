"""Coleta completa para a vitrine pública (spec 012, FR-194).

Roda, em sequência e uma vez, as mesmas coletas que o agendador faz ao longo do dia, num banco
recém-criado (o do workflow `demo.yml`). A falha de uma fonte não para as outras: a página Estado
do sistema da vitrine mostra o resultado real de cada uma.

    python scripts/demo_collect.py --backfill-minutes 8

Sai com código 1 só se não houver setores de risco no banco (desta coleta ou de uma anterior,
recuperada do cache): sem eles a vitrine não tem o que mostrar.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.ingestion import runner
from app.models.tables import hydro_risk_sectors


def describe(result: Any) -> str:
    """Resumo curto de qualquer retorno das coletas (RunOutcome, listas, resumos)."""
    if result is None:
        return "nada a fazer"
    if isinstance(result, list):
        return "; ".join(f"{code}: {describe(item)}" for code, item in result)
    status = getattr(result, "status", None)
    if status is not None:
        error = getattr(result, "error", None)
        return f"{status}" + (f" ({error})" if error else "")
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        fields = (
            f"{k}={v}"
            for k, v in dataclasses.asdict(result).items()
            if not isinstance(v, dict | list)
        )
        return f"{type(result).__name__}(" + ", ".join(fields)[:200] + ")"
    return type(result).__name__


async def step(name: str, action: Callable[[], Awaitable[Any]], summary: dict[str, str]) -> Any:
    start = time.monotonic()
    try:
        result = await action()
    except Exception as exc:
        summary[name] = f"ERRO: {type(exc).__name__}: {exc}"[:300]
        print(f"[{time.monotonic() - start:6.1f}s] {name}: {summary[name]}", flush=True)
        return None
    summary[name] = describe(result)
    print(f"[{time.monotonic() - start:6.1f}s] {name}: {summary[name]}", flush=True)
    return result


async def collect(backfill_minutes: float) -> dict[str, str]:
    settings = get_settings()
    summary: dict[str, str] = {}
    await step("subprefeituras", lambda: runner.run_subprefecture_sync(settings), summary)
    await step("geosampa", lambda: runner.run_geosampa_sync(settings), summary)
    await step("estações INMET", lambda: runner.run_station_sync(settings), summary)
    await step("previsão", lambda: runner.run_forecast(settings), summary)
    await step("tabela IAG/USP", lambda: runner.run_iag_import(settings), summary)

    deadline = time.monotonic() + backfill_minutes * 60
    rounds = 0
    while time.monotonic() < deadline:
        outcome = await step(
            "reanálise (carga)", lambda: runner.run_archive_backfill(settings), summary
        )
        rounds += 1
        if outcome is None or getattr(outcome, "status", "") not in ("SUCCESS", "PARTIAL"):
            break
    summary["reanálise (rodadas)"] = str(rounds)
    await step("reanálise (atualização)", lambda: runner.run_archive_update(settings), summary)

    await step("relevo e hidrografia", lambda: runner.run_geo_refresh(settings), summary)
    await step("risco", lambda: runner.run_flood_risk(settings), summary)
    # Avaliação retrospectiva do motor (spec 015): arquivo de previsões e retroteste.
    await step("previsões arquivadas", lambda: runner.run_forecast_archive(settings), summary)
    await step("avaliação do motor", lambda: runner.run_risk_evaluation(settings), summary)
    await step("Defesa Civil", lambda: runner.run_idap(settings), summary)
    await step("avisos INMET", lambda: runner.run_inmet_warnings(settings), summary)
    await step("alertas do sistema", lambda: runner.run_alert_evaluation(settings), summary)
    active = await _active_sectors(settings.database_url)
    summary["setores no banco"] = str(active)
    summary["setores ok"] = "sim" if active > 0 else "não"
    return summary


async def _active_sectors(database_url: str) -> int:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            query = select(func.count()).where(hydro_risk_sectors.c.active.is_(True))
            return int((await conn.execute(query)).scalar_one())
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backfill-minutes", type=float, default=8.0)
    args = parser.parse_args(argv)
    summary = asyncio.run(collect(args.backfill_minutes))
    print("\nResumo da coleta:")
    for name, value in summary.items():
        print(f"  {name:28} {value}")
    return 0 if summary.get("setores ok") == "sim" else 1


if __name__ == "__main__":
    sys.exit(main())

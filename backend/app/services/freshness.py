"""Classificação de frescor das fontes (BR-020). Função pura."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Freshness = Literal["FRESH", "DELAYED", "STALE", "UNAVAILABLE", "UNKNOWN"]
Reason = Literal[
    "ok",
    "delayed",
    "stale",
    "missing_credentials",
    "last_run_failed",
    "never_collected",
    "disabled",
]


@dataclass(frozen=True)
class FreshnessResult:
    freshness: Freshness
    reason: Reason


def classify_freshness(
    *,
    now: datetime,
    last_success_at: datetime | None,
    expected_interval_s: int,
    last_run_status: str | None,
    credentials_missing: bool = False,
    enabled: bool = True,
) -> FreshnessResult:
    """FRESH até 1,5x o intervalo esperado; DELAYED até 3x; STALE acima.

    UNAVAILABLE quando falta credencial ou a última coleta falhou; UNKNOWN se nunca coletou.
    Nunca considera um dado antigo como atual só por estar no banco (Constituição §7).
    """
    if not enabled:
        return FreshnessResult("UNAVAILABLE", "disabled")
    if credentials_missing:
        return FreshnessResult("UNAVAILABLE", "missing_credentials")
    if last_run_status == "FAILED":
        return FreshnessResult("UNAVAILABLE", "last_run_failed")
    if last_success_at is None:
        return FreshnessResult("UNKNOWN", "never_collected")
    age_s = (now - last_success_at).total_seconds()
    if age_s <= 1.5 * expected_interval_s:
        return FreshnessResult("FRESH", "ok")
    if age_s <= 3 * expected_interval_s:
        return FreshnessResult("DELAYED", "delayed")
    return FreshnessResult("STALE", "stale")

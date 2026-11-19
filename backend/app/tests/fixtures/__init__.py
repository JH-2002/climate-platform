"""Respostas reais gravadas no smoke test de 2026-11-19 (dados de teste, nunca de produção)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


INMET_STATIONS_SP = "inmet_estacoes_sp_2026-11-19.json"
OPEN_METEO_SP = "open_meteo_forecast_sao_paulo_2026-11-19.json"

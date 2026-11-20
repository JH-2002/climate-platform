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

# Recortes reais do WFS do GeoSampa gravados em 2026-11-19 (camadas completas filtradas por id):
# 6 setores, 2 manchas de 100 anos e as ocorrências próximas a esses setores (+1 distante).
GEOSAMPA_SECTORS = "geosampa_risco_hidrologico_2026-11-19.json"
GEOSAMPA_FLOOD_EXTENT = "geosampa_area_inundavel_2026-11-19.json"
GEOSAMPA_OCC_ALAGAMENTO = "geosampa_ocorrencia_alagamento_2026-11-19.json"
GEOSAMPA_OCC_INUNDACAO = "geosampa_ocorrencia_inundacao_2026-11-19.json"

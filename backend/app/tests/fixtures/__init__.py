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

# Open-Meteo Historical (reanálise), ponto -23.57,-46.62, nov/2025–jan/2026, gravada em 2026-11-19.
OPEN_METEO_ARCHIVE_SP = "open_meteo_archive_sao_paulo_2025-11_2026-01.json"

# Hidrografia do GeoSampa gravada em 2026-11-20 (spec 008): bacias que contêm os 6 setores acima
# (contorno simplificado para ~40 vértices e coordenadas com 5 casas), 8 trechos de drenagem
# perto deles e 3 piscinões da bacia do Aricanduva. Atributos sem alteração.
GEOSAMPA_BASINS = "geosampa_bacia_hidrografica_2026-11-20.json"
GEOSAMPA_DRAINAGE = "geosampa_drenagem_2026-11-20.json"
GEOSAMPA_RESERVOIRS = "geosampa_reservatorio_amortecimento_2026-11-20.json"

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


def load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# Alertas (spec 009), gravados em 2026-11-24/25 e recortados (SOURCES.md §15 a §17):
# - IDAP: 4 dos 161 alertas do feed (3 sobre a capital, 1 sobre Sorocaba), sem alteração;
# - INMET: RSS com 4 dos 64 avisos e as mensagens CAP de 3 deles, com a lista de municípios
#   reduzida (o original lista centenas) e o polígono do 56500 com 1 a cada 3 vértices;
# - GeoSampa: 3 das 32 subprefeituras (Lapa, Sé, Pinheiros), contorno com ~25 vértices.
IDAP_FEED = "idap_cap_feed_2026-11-24.xml"
INMET_RSS = "inmet_avisos_rss_2026-11-24.xml"
INMET_CAP_ALERT = "inmet_cap_56503_2026-11-24.xml"
INMET_CAP_STORM = "inmet_cap_56501_2026-11-24.xml"
INMET_CAP_CANCEL = "inmet_cap_56500_2026-11-24.xml"
GEOSAMPA_SUBPREFECTURES = "geosampa_subprefeitura_2026-11-24.json"

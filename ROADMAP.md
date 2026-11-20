# ROADMAP

Cada fase tem spec, plan, tasks e critérios de conclusão próprios. Uma fase só começa depois que a anterior cumpre a Definition of Done.

| Fase | Nome | Spec | Entregável principal | Bloqueios externos |
|---|---|---|---|---|
| 0 ✅ | Discovery & Specification | — | Constituição, arquitetura, fontes, specs 001–002 | — |
| 1 ✅ | Foundation | 001 | Ambiente Docker, API com health, frontend shell, CI | Docker Desktop |
| 2 ✅* | Data Ingestion | 002, 002b | INMET + Open-Meteo + importador CEMADEN | **Token INMET** |
| 3 ✅* | Weather Dashboard | 003 | Clima atual, histórico, acumulados, previsão, locais | — |
| 4 ✅ | Geospatial Map | 004 | Mapa 2D/3D (MapLibre) com relevo, estações, chuva prevista e camadas | — |
| 5 | Flood Risk Engine | 005 | Modelo heurístico v0 experimental, explicável (setores do GeoSampa × chuva prevista) | — (ANA e CGE viram melhorias) |
| 6 | Analytics | 006 | KPIs, Analytics Studio, Data Explorer, insights por regra | — |
| 7 | Simulation Lab | 007 | Motor com seed, modos SIMULATION/HYBRID | — |
| 8 | Geo Intelligence 3D | 008 | Terreno Copernicus DEM, camadas 3D, fallback 2D | — |
| 9 | Alerts | 009 | Regras, alertas oficiais × internos, notificações | Fonte de alertas oficiais |
| 10 | Report Center | 010 | PDF/CSV/JSON assíncronos | — |
| 11 | Hardening | 011 | Segurança, performance, a11y, E2E, deploy | Hospedagem |

## Ordem de prioridade dentro do produto
1. Dados reais confiáveis e rastreáveis (Fases 1–2).
2. Valor imediato para o usuário cotidiano (Fases 3–4).
3. Diferencial analítico (Fases 5–6).
4. Diferencial de demonstração (Fases 7–8).
5. Operação (Fases 9–11).

\* Fases 2 e 3 concluídas exceto as observações medidas do INMET (aguardando token).

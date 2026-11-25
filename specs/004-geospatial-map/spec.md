# Spec 004 — Mapa geoespacial 2D/3D

> Status: **Concluída** (2026-11-19) · Fase: 4 · Plano: [plan.md](plan.md) · Tarefas: [tasks.md](tasks.md)

## Contexto
O painel (spec 003) responde "como está o tempo aqui". Falta responder **onde**: ver estações, pontos de previsão e a chuva prevista distribuídos no território. A pedido do responsável, o mapa é **2D e 3D no mesmo componente** (ADR-009), em vez de um mapa 2D agora e 3D só na Fase 8.

## Objetivo
Página **Mapa** (`/map`) com mapa base, relevo real em 3D, camadas de estações, pontos de previsão (chuva prevista em 24 h) e locais salvos, com legenda, detalhes ao clicar e uma alternativa em lista.

## Escopo
**Incluído:** API GeoJSON das camadas; página `/map` com modo 2D e 3D (relevo, inclinação, colunas de chuva); alternância de camadas; legenda; popups; lista acessível; estado na URL; reserva 2D automática sem WebGL.

**Fora do escopo:** zonas de risco e ocorrências (Fase 5); bacias, drenagem e terreno analítico em Three.js (Fase 8); busca de endereços (geocodificação); agrupamento de marcadores (com menos de 50 marcadores não é necessário — reavaliar quando entrarem pluviômetros).

## User stories
- **US-040** Como usuário, quero ver no mapa onde estão as estações oficiais e qual a situação de cada uma.
- **US-041** Como usuário, quero ver onde há chuva prevista nas próximas 24 h.
- **US-042** Como analista, quero ver o relevo em 3D para entender por onde a água escoa.
- **US-043** Como usuário com equipamento simples ou que prefere menos movimento, quero o mapa plano.

## Requisitos funcionais
- **FR-050** `GET /api/v1/map/region` devolve a região de interesse como Feature GeoJSON (polígono) com nome.
- **FR-051** `GET /api/v1/map/layers/stations?bbox=` devolve FeatureCollection de pontos com código, nome, situação e fonte.
- **FR-052** `GET /api/v1/map/layers/forecast-points` devolve FeatureCollection com a estimativa de temperatura para agora, a chuva prevista em 24 h (e se o intervalo está completo), o horário da coleta e `kind = FORECAST`.
- **FR-053** A página `/map` mostra mapa base com atribuição, a região, e as camadas: Estações, Chuva prevista (24 h), Meus locais. Cada camada pode ser ligada e desligada.
- **FR-054** Botão 2D/3D. Em 3D: relevo real, inclinação e chuva prevista como colunas com altura proporcional. Em 2D: mapa plano e chuva como círculos de tamanho proporcional.
- **FR-055** Clicar num elemento abre detalhes com link para o painel do clima naquele ponto.
- **FR-056** Legenda com cores **e** textos (situação das estações; faixas de chuva).
- **FR-057** Abaixo do mapa, lista com as mesmas informações (estações e pontos de previsão) — o mapa não é a única forma de acesso (Constituição §11, item 18).
- **FR-058** Sem WebGL, a página explica e mostra só a lista; com `prefers-reduced-motion`, sem animações de câmera.
- **FR-059** Modo e camadas ficam na URL (`?modo=3d&camadas=estacoes,chuva`).

## Requisitos não funcionais
- **NFR-050** A biblioteca de mapa é carregada só na página `/map` (import dinâmico).
- **NFR-051** Mapa base e relevo trocáveis por configuração (`NEXT_PUBLIC_MAP_STYLE_URL`, `NEXT_PUBLIC_TERRAIN_TILES_URL`).
- **NFR-052** Atribuições exibidas: OpenFreeMap/OpenMapTiles/OpenStreetMap, Terrain Tiles (Mapzen/AWS), Open-Meteo, INMET.

## Regras de negócio
- **BR-050** Faixas de chuva prevista em 24 h: 0 (sem chuva), até 5 mm (fraca), 5–25 mm (moderada), 25–50 mm (forte), acima de 50 mm (muito forte). Faixas visuais, não alertas.
- **BR-051** Altura das colunas em 3D proporcional à chuva prevista (escala linear com teto), indicada na legenda.
- **BR-052** Chuva prevista incompleta (`complete = false`) é marcada como parcial no popup e na lista.

## Critérios de aceite
- **AC-050** *Given* estações sincronizadas, *When* abro `/map`, *Then* vejo A701 e A771 na região e na lista abaixo do mapa.
- **AC-051** *Given* o modo 3D, *When* ativo, *Then* o mapa inclina, o relevo aparece e a chuva vira coluna; *When* volto a 2D, *Then* fica plano.
- **AC-052** *Given* camadas desligadas na URL, *When* abro o link, *Then* a página respeita o estado.
- **AC-053** *Given* navegador sem WebGL, *When* abro `/map`, *Then* vejo a explicação e a lista.
- **AC-054** *Given* a API de camadas, *When* consulto, *Then* recebo GeoJSON válido (`type`, `features`, coordenadas `[lon, lat]`).

## Dependências
Specs 002/003. MapLibre GL JS; OpenFreeMap (estilo `liberty`); AWS Terrain Tiles (Terrarium) — acesso testado em 2026-11-19 a partir da rede do responsável (200, CORS liberado).

## Riscos e limitações
- Serviços públicos gratuitos sem garantia de disponibilidade: URLs configuráveis; se o mapa base falhar, a lista continua funcionando.
- Relevo do Terrain Tiles é um modelo de terreno de resolução moderada: serve para visualização, não para análise hidrológica (que fica para a Fase 8, com o Copernicus DEM).

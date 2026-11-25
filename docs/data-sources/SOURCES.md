# Fontes de Dados — Registro de Validação (Fase 0)

> Data da validação: 2026-11-19
> Método: pesquisa em documentação oficial, manuais e repositórios públicos.
> **Teste ao vivo (T014):** executado em 2026-11-19 a partir da rede do responsável — ver [smoke-results.md](smoke-results.md). INMET (lista de estações) e Open-Meteo confirmados com respostas reais gravadas como fixtures de teste.

Legenda de status:
- **VIÁVEL** — acesso programático documentado e compatível com o projeto.
- **CONDICIONAL** — exige credencial, cadastro ou confirmação.
- **MANUAL** — dados disponíveis apenas por download em portal (não automatizável sem autorização).
- **ADIADA** — não necessária na fase atual.

---

## 1. INMET — Estações meteorológicas automáticas

| Campo | Valor |
|---|---|
| Responsável | Instituto Nacional de Meteorologia (MAPA) |
| URL oficial | https://portal.inmet.gov.br · https://tempo.inmet.gov.br |
| Base da API | `https://apitempo.inmet.gov.br` |
| Método | REST/JSON |
| Endpoints documentados por terceiros | `GET /estacoes/T` (lista de estações automáticas, sem token) · `GET /token/estacao/{inicio}/{fim}/{codigo}/{token}` (dados horários, **com token**) |
| Rota antiga sem token | `GET /estacao/{inicio}/{fim}/{codigo}` — há relatos de HTTP 404 em 2026; **não confiar** |
| Autenticação | Token solicitado ao INMET (preferencialmente por e-mail institucional) |
| Formato | JSON; horários em UTC |
| Frequência | Horária; o portal informa serviço de dados horários dos últimos 90 dias |
| Variáveis | temperatura, umidade, pressão, vento (vel., dir., rajada), precipitação, radiação |
| Histórico | BDMEP / "Dados Históricos" (arquivos anuais CSV) — **verificar URL e formato na T014** |
| Licença | Dados públicos federais; termo de uso específico **não localizado** — registrar ao obter o token |
| Status | **VIÁVEL** para lista de estações (testado: 200, 675 estações) · **CONDICIONAL** para dados horários (rota sem token testada: 204) |

**Decisão:** INMET é a fonte primária de observações (ADR-003). Sem token, o sistema exibe observações como `UNAVAILABLE` — não substitui por outra fonte silenciosamente.

**Ação do usuário:** solicitar token ao INMET pelo e-mail cadastro.act@inmet.gov.br (endereço indicado na documentação do pacote INMET.jl; confirmar se o INMET responder com outro canal).

---

## 2. CEMADEN — Pluviômetros automáticos

| Campo | Valor |
|---|---|
| Responsável | Centro Nacional de Monitoramento e Alertas de Desastres Naturais (MCTI) |
| URL oficial | https://mapainterativo.cemaden.gov.br |
| Método | Visualização no Mapa Interativo; download mensal por UF/município com "confirmação de segurança" (captcha) |
| API pública documentada | **Não localizada.** Existem endpoints internos usados pelo mapa (ex.: gráficos PHP), mas sem documentação nem termo de uso → **não usar** sem autorização |
| Frequência | Acumulados a cada 10 min; horários em UTC; histórico desde 2013 |
| Formato do download | CSV mensal (verificar layout na importação) |
| Status | **MANUAL** |

**Decisão:** na Fase 2, implementar um **importador de arquivos CSV** baixados manualmente (com proveniência: arquivo, data do download, hash). Coleta automática somente com autorização formal do CEMADEN (contato via Fale Conosco / SIC).

---

## 3. ANA — HidroWebService / Hidro-Telemetria

| Campo | Valor |
|---|---|
| Responsável | Agência Nacional de Águas e Saneamento Básico |
| URL | `https://www.ana.gov.br/hidrowebservice/` (Swagger em `/swagger-ui/index.html`) · legado SOAP: `https://telemetriaws1.ana.gov.br/ServiceANA.asmx` |
| Método | REST com autenticação (credencial → token de curta duração; clientes de terceiros renovam a cada ~10 min) |
| Variáveis | nível (cota), vazão, chuva de estações telemétricas |
| Frequência | Telemetria horária / 15 min |
| Status | **CONDICIONAL** (cadastro) |

**Decisão:** fonte hidrológica prioritária para a Fase 5 (níveis de rio na RMSP). Adiada da Fase 2.

---

## 4. SGB — SACE (Sistema de Alerta de Eventos Críticos)

| Campo | Valor |
|---|---|
| Responsável | Serviço Geológico do Brasil (SGB/CPRM) |
| URL | https://www.sgb.gov.br/sace · portais por bacia (ex.: `sace.sgb.gov.br/cai`) |
| Método | Portais web e boletins por bacia; **API pública não localizada** |
| Cobertura | Sistemas de alerta por bacia (Caí, Taquari, Uruguai, Guaíba, Doce, Xingu, São Francisco etc.). Cobertura da cidade de São Paulo **não confirmada** |
| Status | **ADIADA** |

---

## 5. CGE — Prefeitura de São Paulo

| Campo | Valor |
|---|---|
| Responsável | Centro de Gerenciamento de Emergências Climáticas (PMSP) |
| URL | https://www.cgesp.org |
| Rede | ~305 postos na RMSP, ~154 na capital |
| Relevância | Altíssima para alagamentos na capital: emite estados de atenção/alerta para alagamentos e mantém registro de pontos de alagamento |
| API pública | **Não localizada** |
| Status | **ADIADA** — investigar dados abertos da PMSP / pedido via LAI na Fase 5 |

**Observação:** os estados de atenção/alerta do CGE são **alertas oficiais** e precisam ser tratados como categoria distinta do risco estimado pelo sistema (Constituição §7).

---

## 6. Open-Meteo — Previsão (complementar)

| Campo | Valor |
|---|---|
| Responsável | Open-Meteo (Suíça), agregando modelos de serviços meteorológicos nacionais |
| URL | `https://api.open-meteo.com/v1/forecast` |
| Autenticação | Nenhuma para uso não comercial |
| Limites (termos) | < 10.000 chamadas/dia, 5.000/hora, 600/minuto; uso não comercial |
| Licença dos dados | CC BY 4.0 — **atribuição obrigatória** |
| Formato | JSON; previsão horária e diária até 7+ dias |
| Status | **VIÁVEL** (testado: 200; vento em km/h por padrão) |

**Decisão:** fonte de **previsão** e de séries **modeladas** (ADR-004). Todo dado da Open-Meteo é rotulado `kind = FORECAST` ou `kind = MODELED`, **nunca** `OBSERVED`. Uso comercial futuro exige plano pago ou self-hosting (código AGPLv3).

---

## 7. Copernicus DEM — Elevação

| Campo | Valor |
|---|---|
| Responsável | ESA / Copernicus |
| Produto | GLO-30 Public (30 m) e GLO-90 |
| Acesso | AWS Open Data, bucket `s3://copernicus-dem-30m/` (sem conta AWS, `--no-sign-request`), Cloud Optimized GeoTIFF, STAC |
| Licença | Gratuita para o público em geral, com termos Copernicus; exige citação |
| Limitação | É um **modelo de superfície (DSM)**: inclui prédios e vegetação — impacta análise de áreas baixas em área urbana densa |
| Status | **VIÁVEL** (Fase 5/8) |

---

## 8. Complementares a investigar (fases futuras)

- **IBGE** — malhas municipais, setores censitários (vulnerabilidade).
- **OpenStreetMap** — rios, vias, infraestrutura (ODbL, atribuição).
- **GeoSampa (PMSP)** — hidrografia, drenagem, manchas de inundação da capital.
- **CPTEC/INPE** — previsão e produtos de radar.
- **Defesa Civil SP** — alertas estaduais.

---

## Resumo para a Fase 2

| Prioridade | Fonte | Uso | Bloqueio |
|---|---|---|---|
| 1 | INMET | Observações horárias | Token |
| 2 | Open-Meteo | Previsão 7 dias | Nenhum |
| 3 | CEMADEN | Pluviometria 10 min (importação manual) | Download manual |

---

## 9. Mapa base e relevo (visualização — Fase 4)

| Fonte | Uso | Acesso | Licença/atribuição | Teste (2026-11-19, rede do responsável) |
|---|---|---|---|---|
| OpenFreeMap (estilo `liberty`) | Mapa base vetorial | `https://tiles.openfreemap.org/styles/liberty`, sem chave, sem cookies | Atribuição obrigatória (OpenFreeMap © OpenMapTiles, dados do OpenStreetMap), exibida automaticamente pelo MapLibre | 200, CORS liberado, 111 camadas |
| AWS Terrain Tiles (Mapzen) | Relevo 3D e sombreamento | `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`, sem chave | Atribuição exigida (ver docs do Joerd/Mapzen) | 200, CORS liberado |

Uso apenas visual. Análise hidrológica e de declividade continua planejada com o Copernicus DEM (Fase 8).

---

## 10. GeoSampa — Prefeitura de São Paulo (Fase 5)

| Campo | Valor |
|---|---|
| Responsável | Prefeitura de São Paulo — SMUL/Geoinfo (distribuição); SIURB (manchas); Defesa Civil/SIGRC (ocorrências) |
| URL | https://geosampa.prefeitura.sp.gov.br · metadados: https://metadados.geosampa.prefeitura.sp.gov.br |
| Serviço | WFS (GeoServer) `http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs` — **sem HTTPS**, sem chave |
| Requisição | `service=WFS&version=2.0.0&request=GetFeature&typeNames=geoportal:<camada>&outputFormat=application/json&srsName=EPSG:4326` |
| Limite | O servidor corta respostas em 30.000 feições (afeta `mancha_inundacao_5/25/100`, que não são usadas na v0) |
| Restrições | Metadados: acesso "sem restrições"; termos da licença **não informados** → registrar atribuição e confirmar antes de uso público |
| Status | **VIÁVEL** (testado em 2026-11-19 a partir da rede do responsável; em produção local desde 2026-11-20: 793 setores, 53 manchas e 630 ocorrências sincronizados pelo Docker) |

Camadas testadas:

| Camada | Feições | Tamanho | Atributos principais | Atualização |
|---|---|---|---|---|
| `risco_hidrologico` | 793 polígonos (R1 59 · R2 365 · R3 298 · R4 71; 69.648 moradias; vistorias 2021–2026) | 1,6 MB | `sg_setor_risco_hidrologico`, `tx_grau_risco_hidrologico`, `tx_tipo_processo`, `qt_moradia`, `nm_subprefeitura`, `nm_bacia_hidrografica`, `dt_vistoria` | Mensal |
| `area_inundavel` | 53 polígonos (todos TR 100 anos) | 0,3 MB | `cd_identificador_area_inundavel`, `qt_tempo_retorno`, `dt_carga` | Conforme necessidade |
| `risco_ocorrencia_alagamento` | 315 pontos (jan–out/2026) | 0,1 MB | `cd_identificador`, `dc_tipo_ocorrencia`, `dt_ocorrencia`, `nm_subprefeitura`, `sg_fonte_original` (SIGRC) | Mensal; anos anteriores só por download |
| `risco_ocorrencia_inundacao` | 315 pontos | 0,1 MB | idem | Mensal |
| `pluviometro` | 90 pontos, sem latitude/longitude nos atributos e carga de 2015 | 35 KB | — | Não usado (sem medições) |

**Observações:**
- `tx_tipo_processo` vem com variações ("INUNDACAO"/"INUNDAÇÃO", quebras de linha, ordem diferente); o adaptador normaliza em um conjunto de processos.
- As ocorrências são registros de atendimento e podem ter subnotificação. Elas servem para ajuste de suscetibilidade, não como verdade de campo.
- Atribuição exibida: "GeoSampa — Prefeitura de São Paulo".

---

## 11. Chuva mensal do IAG/USP — Água Funda (Fase 6)

| Campo | Valor |
|---|---|
| Responsável | Instituto de Astronomia, Geofísica e Ciências Atmosféricas da USP (estação de Água Funda); publicação e elaboração: Prefeitura de São Paulo (SMUL/Geoinfo) |
| URL | https://prefeitura.sp.gov.br/documents/d/licenciamento/precipitacao_pluviometrica_1933_2025 |
| Formato | Página web com tabela em texto (vírgula decimal, ponto de milhar): ano, 12 meses e total anual, mais normais 1933–1960, 1961–1990 e 1991–2020 |
| Período | 1933–2025, sem falhas |
| Tipo | `OBSERVED` (pluviômetro) |
| Revisão | Nota da página: revisão completa dos dados de 2024 e anteriores feita em 2025 com o IAG-USP |
| Referência publicada | Normal 1991–2020: 1.559,2 mm/ano |
| API | Não há. Atualização anual assistida por script, com conferência mês × total |
| Licença | Dado público municipal; termos não informados → atribuição "IAG/USP — Estação Água Funda; publicação: Prefeitura de São Paulo (SMUL/Geoinfo)" |
| Status | **VIÁVEL** (lida em 2026-11-19) |

Representa a zona sul da capital (Água Funda), não a cidade inteira.

## 12. Open-Meteo Historical API — reanálise ERA5/ERA5-Land (Fase 6)

| Campo | Valor |
|---|---|
| Responsável | Open-Meteo, com dados do Copernicus/ECMWF (ERA5, ERA5-Land) |
| URL | `https://archive-api.open-meteo.com/v1/archive` |
| Autenticação | Nenhuma (uso não comercial) |
| Licença | CC BY 4.0 (atribuição obrigatória); dados ERA5 sob a licença Copernicus |
| Variáveis usadas | `precipitation_sum`, `temperature_2m_max`, `temperature_2m_min`, `temperature_2m_mean` (diárias, fuso `America/Sao_Paulo`) |
| Período | 1991-01-01 até ontem (dias recentes revisados pela fonte) |
| Tipo | `MODELED` |
| Teste (2026-11-19, rede do responsável) | HTTP 200; 13.106 dias sem falhas para 1991–2026; ~11 s e ~490 KB por ponto; vários pontos por chamada aceitos |
| Limites | Uma consulta de 35 anos conta como várias chamadas no limite gratuito (10 mil/dia): carga inicial um ponto por vez |
| Status | **VIÁVEL** |

Características medidas na grade de 12 pontos (1991–2020):
- **Células de chuva:** cerca de 4 séries distintas de chuva entre os 12 pontos, com o mesmo máximo diário em grupos de pontos.
- **Total anual:** de ~1.290 mm (oeste e norte) a ~2.120 mm (extremo sul).
- **Viés:** no centro, ~1.366 mm/ano, ~12% abaixo da normal medida (1.559 mm, IAG/USP).
- **Uso:** comparações de um período com ele mesmo no mesmo ponto (anomalias e percentis). Não serve para valores absolutos de chuva extrema.

## 13. GeoSampa — hidrografia (Fase 8)

| Campo | Valor |
|---|---|
| Responsável | Prefeitura de São Paulo (SMUL/Geoinfo) |
| URL | `http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs` (mesmo WFS da §10) |
| Camadas | `bacia_hidrografica` (269 bacias e sub-bacias), `drenagem` (28.366 trechos, com o tipo: estado natural, canalizado a céu aberto, canalizado subterrâneo, lago), `reservatorio_amortecimento` (72 piscinões, com volume em parte deles) |
| Formato | GeoJSON com `srsName=EPSG:4326`; uma requisição por camada |
| Teste (2026-11-20) | Bacias 5,4 MB em 0,6 s; drenagem 28,5 MB em 2,8 s; piscinões 0,3 MB em 0,1 s |
| Frequência no sistema | A cada 30 dias (`geo.refresh` pula se a última coleta tem menos de 30 dias) |
| Tipo | `OBSERVED` (cadastro oficial) |
| Licença | Dado público municipal → atribuição "GeoSampa — Prefeitura de São Paulo" |
| Status | **VIÁVEL**; carga real em 2026-11-24: os 793 setores de risco ficaram dentro de alguma bacia |

Também existem no WFS curvas de nível, pontos cotados, declividade (2015) e a grade das folhas do LiDAR 2020. O LiDAR (MDT/MDS 1:1000) é baixado folha a folha no portal, em nuvens de pontos (5.401 folhas): não dá para automatizar para a cidade inteira.

## 14. Copernicus DEM GLO-30 — elevação (Fase 8)

| Campo | Valor |
|---|---|
| Responsável | ESA / Copernicus (dados DLR e Airbus) |
| URL | `https://copernicus-dem-30m.s3.amazonaws.com/<bloco>/<bloco>.tif` |
| Blocos usados | `Copernicus_DSM_COG_10_S24_00_W047_00_DEM` (42 MB) e `…_S25_00_W047_00_DEM` (4,8 MB, quase todo mar) |
| Autenticação | Nenhuma |
| Formato | GeoTIFF otimizado (COG), float32, grade de 1" (~28 m em longitude e ~31 m em latitude na cidade) |
| Tipo | `DERIVED` nas métricas; modelo de **superfície** (prédios e árvores entram na elevação) |
| Licença | Uso livre com atribuição: "Produced using Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA, all rights reserved" |
| Uso no sistema | Download único e recorte da região com 0,02° de folga (`/data/dem`); terreno por setor e bacia, perfil e elevação de um ponto |
| Status | **VIÁVEL**; recorte real em 2026-11-24 com ~28 m de resolução |

Limitação medida: 351 dos 793 setores de risco (44%) têm menos de 4 células de 30 m (mediana: 4 células). Para esses setores, a elevação é marcada como "pouca amostra".

## 15. IDAP — alertas da Defesa Civil (Fase 9)

| Campo | Valor |
|---|---|
| Responsável | Ministério da Integração e do Desenvolvimento Regional — Secretaria Nacional de Proteção e Defesa Civil |
| URL | `https://idapfile.mdr.gov.br/idap/api/rss/cap` |
| O que é | Os alertas que as Defesas Civis (estaduais e municipais) mandam à população por SMS, WhatsApp, Google Alertas Públicos e Defesa Civil Alerta |
| Autenticação | Nenhuma; `robots.txt` responde 404 (sem regras) |
| Formato | Feed Atom; cada `<entry>` traz uma mensagem CAP 1.2 com polígono |
| Teste (2026-11-25 01:30 UTC) | 16,6 MB, 161 alertas das ~12 h anteriores, de 20 remetentes; 46 da Defesa Civil do Estado de SP, vários sobre a capital (ex.: "Chuva se espalhando pelas Zonas Oeste e Sul de São Paulo"). Só `msgType` "Alert". 48 alertas trazem geocódigo IBGE; os de SP não |
| Particularidade | O `areaDesc` dos alertas da Defesa Civil de SP vem como "SÃO PAULO/SP" para todo o estado: a área vale pelo polígono |
| Frequência no sistema | A cada 10 min (o feed guarda só ~12 h) |
| Tipo | Alerta oficial (categoria `CIVIL_DEFENSE`) |
| Licença | Alerta público oficial; atribuição "Fonte: Defesa Civil (IDAP/MIDR)" |
| Status | **VIÁVEL** |

## 16. INMET — avisos meteorológicos (Alert-AS, Fase 9)

| Campo | Valor |
|---|---|
| Responsável | Instituto Nacional de Meteorologia (INMET) |
| URL | RSS `https://apiprevmet3.inmet.gov.br/avisos/rss`; CAP de cada aviso em `…/avisos/rss/<número>` |
| Autenticação | Nenhuma |
| Formato | RSS 2.0 (UTF-8, servido sem `charset` no cabeçalho) + mensagem CAP 1.2 por aviso, com polígono e o parâmetro `Municipios` ("São Paulo - SP (3550308), …") |
| Teste (2026-11-25 01:35 UTC) | 64 avisos no RSS; 29 citando a capital. CAP de 40 KB a 135 KB cada. Usa `Alert`, `Update` e `Cancel` (com `references`) |
| Severidade | CAP Moderate/Severe/Extreme = amarelo "Perigo potencial", laranja "Perigo", vermelho "Grande perigo" |
| Frequência no sistema | A cada 30 min; o CAP só é baixado para avisos ainda não vistos |
| Tipo | Aviso meteorológico oficial (categoria `WEATHER_WARNING`) |
| Licença | "O conteúdo deste site poderá ser reproduzido desde que citada a fonte" (comentário do próprio RSS) → "Fonte: INMET — Alert-AS" |
| Status | **VIÁVEL** |

## 17. GeoSampa — subprefeituras (Fase 9)

| Campo | Valor |
|---|---|
| Camada | `subprefeitura` no WFS da §10 |
| Conteúdo | 32 polígonos, com sigla, área e a região em 5 (`nm_regiao_05`: Norte, Sul, Leste, Oeste, Centro) e em 8 |
| Teste (2026-11-24) | 2,35 MB; atualizada em 16/11/2026 |
| Uso | Limite real do município (união das 32) para a interseção dos alertas, e lista das subprefeituras atingidas |
| Frequência no sistema | A cada 24 h |
| Status | **VIÁVEL** |

As fixtures das §15 a §17 são recortes das respostas reais (ver `app/tests/fixtures/__init__.py`).

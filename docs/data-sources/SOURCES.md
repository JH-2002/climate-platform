# Fontes de Dados — Registro de Validação (Fase 0)

> Data da validação: 2026-11-19
> Método: pesquisa em documentação oficial, manuais e repositórios públicos.
> **Limitação importante:** nenhuma chamada HTTP real foi executada nesta fase. O ambiente de trabalho (container e shell local) estava sem acesso de rede a esses domínios. Toda fonte abaixo tem status **"documentada, não testada ao vivo"** até a tarefa T014 (smoke test de fontes) da spec 001 ser executada na máquina do desenvolvedor.

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
| Status | **CONDICIONAL** (token) |

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
| Status | **VIÁVEL** |

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

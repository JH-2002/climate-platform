# ADR-003 — INMET como fonte primária de observações

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
O sistema precisa de observações meteorológicas reais (temperatura, umidade, pressão, vento, chuva). Ver `docs/data-sources/SOURCES.md`.

## Opções consideradas
1. **INMET (apitempo)** — oficial, horário, nacional; dados horários exigem token.
2. CEMADEN — pluviometria a cada 10 min, mas sem API pública documentada (download manual com captcha).
3. Open-Meteo — sem token, mas produz dados de **modelo**, não de estação.

## Decisão
INMET é a fonte primária de observações. Open-Meteo **não** é usado como substituto de observação. CEMADEN entra como importação manual de CSV.

## Consequências
- Bloqueio externo: é preciso obter o token do INMET antes da Fase 2 rodar com dados reais.
- Sem token: a UI mostra observações como `UNAVAILABLE` com motivo "credencial ausente"; o restante (previsão, mapa de estações) continua funcionando.
- O token fica em `INMET_TOKEN` (variável de ambiente); nunca em log nem em URL registrada (o adapter mascara o path).

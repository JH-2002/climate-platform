# ADR-004 — Open-Meteo para previsão

**Status:** Aceita · **Data:** 2026-11-19

## Contexto
A dashboard exige previsão de 7 dias. Não foi localizada documentação estável de API de previsão do INMET/CPTEC para consumo programático.

## Decisão
Usar `api.open-meteo.com/v1/forecast` para previsão horária e diária, com:
- `kind = FORECAST` em todos os registros; `model` registrado quando informado.
- Atribuição CC BY 4.0 visível na UI e nos relatórios.
- Cache por célula de grade (~0,1°) por 60 min, para ficar muito abaixo do limite de 10.000 chamadas/dia.

## Consequências
- Uso **não comercial** apenas. Se o projeto virar produto comercial: plano pago ou self-hosting (AGPLv3) — registrar nova ADR.
- Previsão de modelo global/regional não captura bem convecção local intensa; a UI deixa isso explícito.
- Reavaliar CPTEC/INPE na Fase 3.

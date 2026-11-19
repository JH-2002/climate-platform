# Plan 003 — Painel do clima

## Decisões
- **ADR-007:** a seção "Agora" usa a previsão horária da hora corrente, rotulada como estimativa de modelo. Não é usada nenhuma API de "condições atuais" de modelo travestida de medição.
- **ADR-008:** locais salvos ficam no `localStorage` do navegador (com tratamento de erro) até existir autenticação.
- **Recharts** para o gráfico de 48 h, com tabela acessível equivalente.

## Backend
| Arquivo | Responsabilidade |
|---|---|
| `app/services/forecast.py` | Ponto mais próximo (PostGIS), séries horária/diária, acumulados (funções puras para pivot e soma) |
| `app/api/v1/weather.py` | `GET /weather/forecast`; relógio injetável (`get_clock`) para testes |

Contrato:
```
GET /api/v1/weather/forecast?lat=&lon=
200 {
  kind: "FORECAST",
  point: {latitude, longitude, distance_km},
  source: {code, name, attribution, freshness, reason, last_success_at},
  issued_at,
  now: {valid_at, air_temperature, precipitation, relative_humidity, wind_speed} | null,
  hourly: [{valid_at, air_temperature, precipitation, relative_humidity, wind_speed}],
  daily: [{date, air_temperature_max, air_temperature_min, precipitation_sum,
           precipitation_probability_max}],
  precipitation_outlook: [{hours, total_mm, complete, hours_available}],
  units: {air_temperature: "°C", precipitation: "mm", relative_humidity: "%", wind_speed: "m/s",
          precipitation_probability_max: "%"}
}
404 Problem Details (sem previsão até 25 km)
```

## Frontend
| Arquivo | Responsabilidade |
|---|---|
| `features/weather/*` | tipos, cliente, hook TanStack Query |
| `features/locations/store.ts` | locais no `localStorage` (puro + testável) |
| `features/locations/useLocations.ts` | estado React sincronizado com o store |
| `components/weather/*` | Agora, gráfico 48 h, tabela 7 dias, chuva prevista, estações próximas, seletor de locais |
| `app/weather/page.tsx` | composição + local na URL |

## Testes
- Unitários backend: pivot horário/diário, acumulados completos/incompletos (AC-042), hora corrente (BR-040).
- Integração: endpoint com a previsão real gravada e relógio fixo em 2026-11-19 (AC-040, AC-041).
- Frontend: store de locais (AC-043), componentes nos estados, axe.

## Ordem
T030 → T031 → T032 → T033 → T034 → T035 → T036 → T037.

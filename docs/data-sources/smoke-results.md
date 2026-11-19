# Smoke test das fontes externas

> Executado em 2026-11-19, por volta de 14:00 (horário de Brasília), a partir da rede do responsável pelo projeto
> (navegador integrado do app Claude, mesma máquina onde roda o Docker). Equivale ao `scripts/smoke_sources.py`;
> o script continua sendo a forma reproduzível de repetir o teste.
> Resultado de um único momento: indica acesso, não disponibilidade contínua.

| Fonte | Finalidade | Resultado | Observações |
|---|---|---|---|
| INMET | Lista de estações (`GET /estacoes/T`, sem token) | **200 — JSON** | 675 estações automáticas; 48 em SP. Campos: `CD_ESTACAO`, `DC_NOME`, `CD_SITUACAO` (`Operante`/`Pane`), `VL_LATITUDE`, `VL_LONGITUDE`, `VL_ALTITUDE` (texto), `SG_ESTADO`, `TP_ESTACAO`, `DT_INICIO_OPERACAO`, `DT_FIM_OPERACAO`, `CD_OSCAR`, `CD_WSI`, `FL_CAPITAL`, `CD_DISTRITO`, `SG_ENTIDADE`. Na capital: **A701 São Paulo – Mirante** e **A771 São Paulo – Interlagos** (operantes); na RMSP, **A755 Barueri** está em `Pane`. Amostra gravada em `backend/app/tests/fixtures/inmet_estacoes_sp_2026-11-19.json`. |
| INMET | Dados horários, rota antiga sem token (`/estacao/{inicio}/{fim}/A701`) | **204 — sem conteúdo** | Confirma que observações horárias exigem token. |
| INMET | Dados horários com token | não testado | Token solicitado por e-mail em 2026-11-19. |
| Open-Meteo | Previsão 7 dias para São Paulo (`/v1/forecast`) | **200 — JSON** | 168 horas + 7 dias. Coordenada ajustada à grade do modelo (−23,5149; −46,6105; elevação 737 m). **Vento em km/h por padrão**; horários sem sufixo `Z` quando `timezone=UTC` (tratar como UTC). Resposta gravada em `backend/app/tests/fixtures/open_meteo_forecast_sao_paulo_2026-11-19.json`. |
| Copernicus DEM | Catálogo STAC GLO-30 (AWS) | alcançável | Resposta recebida (status não visível em requisição sem CORS). |
| ANA | HidroWebService (Swagger) | alcançável | Idem. |
| CEMADEN | Mapa Interativo | alcançável | Idem; sem API documentada (download manual). |
| SGB | Portal SACE | alcançável | Idem; sem API documentada. |

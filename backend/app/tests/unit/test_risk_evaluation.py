"""Avaliação retrospectiva do motor (spec 015): métricas à mão, vazamento e calibração."""

from datetime import UTC, date, datetime

import pytest

from app.ingestion.forecast_archive_jobs import start_day
from app.integrations.open_meteo.historical_forecast import build_params, parse_historical_forecast
from app.risk.coefficients import DEFAULT_COEFFICIENTS, Category
from app.risk.evaluation import (
    CALIBRATION_FACTORS,
    Contingency,
    best_factor,
    by_month,
    contingency,
    day_units,
    nearby_counts,
    normalize_name,
    reliability,
    scaled,
)

D1, D2 = date(2026, 2, 10), date(2026, 3, 5)
SUB = {1: "SE", 2: "SE", 3: "LAPA", 4: "LAPA"}


def test_nomes_de_subprefeitura_comparaveis() -> None:
    assert normalize_name("São Miguel Paulista") == "SAO MIGUEL PAULISTA"
    assert normalize_name("  Cidade   Ademar ") == "CIDADE ADEMAR"
    assert normalize_name("M'Boi Mirim") == "M BOI MIRIM"
    assert normalize_name("Aricanduva/Vila Formosa") == "ARICANDUVA VILA FORMOSA"
    assert normalize_name("Casa Verde-Cachoeirinha") == "CASA VERDE CACHOEIRINHA"
    assert normalize_name(None) == ""


def test_dia_subprefeitura_usa_a_maior_categoria_e_ignora_desconhecido() -> None:
    cats = {1: Category.LOW, 2: Category.HIGH, 3: Category.UNKNOWN, 4: Category.UNKNOWN}
    units = day_units(D1, cats, SUB, {(D1, "SE")})
    assert [(u.subprefecture, u.max_category, u.observed) for u in units] == [
        ("SE", Category.HIGH, True)
    ]  # LAPA só com desconhecido fica de fora (FR-211)


def test_metricas_batem_com_o_calculo_a_mao() -> None:
    """AC-210: 2 acertos, 1 falha, 1 alarme falso, 6 negativos corretos."""
    table = Contingency(hits=2, misses=1, false_alarms=1, correct_negatives=6)
    assert table.total == 10 and table.events == 3
    assert table.pod == pytest.approx(2 / 3)
    assert table.far == pytest.approx(1 / 3)
    assert table.csi == pytest.approx(2 / 4)
    assert table.bias == pytest.approx(3 / 3)
    assert table.base_rate == pytest.approx(3 / 10)
    assert Contingency().pod is None  # sem eventos, a métrica não existe


def test_contingencia_confiabilidade_e_mes() -> None:
    occ = {(D1, "SE"), (D2, "LAPA")}
    units = [
        *day_units(D1, {1: Category.CRITICAL, 3: Category.LOW}, SUB, occ),  # SE acerto, LAPA neg
        *day_units(D2, {1: Category.HIGH, 3: Category.MODERATE}, SUB, occ),  # SE alarme, LAPA falha
    ]
    table = contingency(units)
    assert (table.hits, table.misses, table.false_alarms, table.correct_negatives) == (1, 1, 1, 1)
    rel = {r["category"]: (r["units"], r["with_occurrence"]) for r in reliability(units)}
    assert rel == {"LOW": (1, 0), "MODERATE": (1, 1), "HIGH": (1, 0), "CRITICAL": (1, 1)}
    months = {m["month"]: (m["hits"], m["misses"], m["false_alarms"]) for m in by_month(units)}
    assert months == {"2026-02": (1, 0, 0), "2026-03": (0, 1, 1)}


def test_ocorrencias_proximas_so_ate_a_vespera() -> None:
    """AC-211: ocorrência no próprio dia não entra no fator do dia."""
    days = {7: [date(2026, 2, 9), date(2026, 2, 10), date(2025, 2, 9)]}
    assert nearby_counts(days, date(2026, 2, 10), 365) == {7: 1}
    assert nearby_counts(days, date(2026, 2, 11), 365) == {7: 2}


def test_calibracao_escala_so_as_faixas_de_chuva() -> None:
    half = scaled(DEFAULT_COEFFICIENTS, 0.5)
    assert half.p1h_thresholds_mm == (5.0, 12.5, 25.0)
    assert half.p24_thresholds_mm == (15.0, 30.0, 50.0)
    assert half.antecedent_threshold_mm == DEFAULT_COEFFICIENTS.antecedent_threshold_mm
    assert CALIBRATION_FACTORS[0] == 0.3 and CALIBRATION_FACTORS[-1] == 1.5
    assert 1.0 in CALIBRATION_FACTORS and len(CALIBRATION_FACTORS) == 13


def test_melhor_fator_desempata_pelo_atual() -> None:
    assert best_factor([(0.8, 0.3), (1.0, 0.3), (1.2, 0.2)]) == 1.0
    assert best_factor([(0.7, 0.41), (1.0, 0.3)]) == 0.7
    assert best_factor([(1.0, None)]) is None


def test_arquivo_de_previsoes_parametros_e_leitura() -> None:
    params = build_params(-23.55, -46.63, date(2026, 1, 1), date(2026, 1, 2))
    assert params["hourly"] == "precipitation" and params["timezone"] == "GMT"
    payload = {
        "hourly_units": {"precipitation": "mm"},
        "hourly": {"time": ["2026-01-01T00:00", "2026-01-01T01:00"], "precipitation": [1.24, None]},
    }
    parsed = parse_historical_forecast(payload)
    assert parsed.missing_values == 1
    assert parsed.values[0].valid_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert parsed.values[0].precipitation_mm == 1.24
    with pytest.raises(ValueError, match="bloco horário"):
        parse_historical_forecast({"error": True, "reason": "limite"})


def test_inicio_da_coleta_revisa_os_ultimos_dias() -> None:
    assert start_day(None) == date(2026, 1, 1)
    assert start_day(date(2026, 11, 24)) == date(2026, 11, 22)

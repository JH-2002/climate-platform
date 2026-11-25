"""T076 — regras de insight IN-01 a IN-06, dos dois lados de cada limite (AC-083)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.analytics.climatology import PeriodComparison
from app.analytics.rules import (
    in01_heavy_forecast,
    in02_month_to_date,
    in03_dry_spell,
    in04_risk_increase,
    in05_source_problem,
    in06_occurrence_concentration,
)


def test_in01_heavy_forecast() -> None:
    insight = in01_heavy_forecast(region="Zona Sul", forecast_24h_mm=42.0, p95_mm=31.4, month=11)
    assert insight is not None and insight.severity == "atencao"
    assert insight.text == (
        "Chuva prevista de 42 mm em 24 h na região Zona Sul, acima de 95% dos dias de novembro "
        "desde 1991 (p95 = 31,4 mm)."
    )
    assert [m.kind for m in insight.metrics] == ["FORECAST", "MODELED"]
    assert in01_heavy_forecast(region="x", forecast_24h_mm=31.3, p95_mm=31.4, month=11) is None
    assert in01_heavy_forecast(region="x", forecast_24h_mm=50, p95_mm=None, month=11) is None


def comparison(ratio: float, days: int = 18) -> PeriodComparison:
    return PeriodComparison(
        current=ratio * 40, reference=40.0, ratio=ratio, days=days, years_used=30
    )


def test_in02_month_to_date() -> None:
    high = in02_month_to_date(region="Centro", comparison=comparison(1.6), month=11)
    assert high is not None
    assert high.text.startswith("Novembro acumula 64 mm até ontem na região Centro, 160%")
    low = in02_month_to_date(region="Centro", comparison=comparison(0.4), month=11)
    assert low is not None and "40%" in low.text
    assert in02_month_to_date(region="Centro", comparison=comparison(1.2), month=11) is None
    assert in02_month_to_date(region="Centro", comparison=comparison(2.0, days=5), month=11) is None
    assert in02_month_to_date(region="Centro", comparison=None, month=11) is None


def test_in03_dry_spell() -> None:
    history = list(range(1, 31))  # p90 = 27,1
    insight = in03_dry_spell(
        region="Norte", current_days=28, historical_max_spells=history, month=8
    )
    assert insight is not None and "28 dias seguidos" in insight.text and "agosto" in insight.text
    assert (
        in03_dry_spell(region="Norte", current_days=27, historical_max_spells=history, month=8)
        is None
    )
    assert (
        in03_dry_spell(region="Norte", current_days=40, historical_max_spells=[5] * 10, month=8)
        is None
    )


def test_in04_risk_increase() -> None:
    assert in04_risk_increase(now_count=12, before_count=1) is not None
    appeared = in04_risk_increase(now_count=1, before_count=0)
    assert appeared is not None and "de 0 para 1" in appeared.text
    assert in04_risk_increase(now_count=8, before_count=3) is None
    assert in04_risk_increase(now_count=50, before_count=None) is None
    assert "alerta" not in appeared.text.lower()


def test_in05_source_problem() -> None:
    when = datetime(2026, 11, 19, 10, 30, tzinfo=UTC)
    stale = in05_source_problem(
        source_name="Open-Meteo", freshness="STALE", reason="stale", last_success_at=when
    )
    assert stale is not None and stale.severity == "atencao"
    assert (
        stale.text
        == "Open-Meteo: coleta desatualizada (última coleta bem-sucedida em 19/11/2026 10:30 UTC)."
    )
    token = in05_source_problem(
        source_name="INMET",
        freshness="UNAVAILABLE",
        reason="missing_credentials",
        last_success_at=None,
    )
    assert token is not None and token.severity == "info" and "credencial" in token.text
    assert (
        in05_source_problem(source_name="x", freshness="FRESH", reason="ok", last_success_at=None)
        is None
    )


def test_in06_occurrence_concentration() -> None:
    insight = in06_occurrence_concentration(
        counts_by_subprefecture={"SAO MIGUEL": 30, "PENHA": 40, "SE": 30}
    )
    assert insight is not None and insight.text.startswith(
        "PENHA concentra 40% das 100 ocorrências"
    )
    assert (
        in06_occurrence_concentration(
            counts_by_subprefecture={"A": 2, "B": 2, "C": 2, "D": 2, "E": 2}
        )
        is None
    )
    assert in06_occurrence_concentration(counts_by_subprefecture={"A": 9}) is None

"""Regras de insight IN-01 a IN-06 (spec 006, BR-080). Puras e reproduzíveis.

Cada insight carrega as métricas que o justificam (valor, limite, período, tipo e fonte).
O texto é uma frase-modelo preenchida com essas métricas: nenhuma causa é inventada.
Limites são `experimental`; mudar um deles exige nova `INSIGHT_RULES_VERSION`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.analytics.climatology import PeriodComparison
from app.analytics.stats import percentile

INSIGHT_RULES_VERSION = "0.1.0-experimental"

Severity = Literal["info", "atencao"]

MONTH_NAMES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


@dataclass(frozen=True)
class Thresholds:
    in01_percentile: float = 95.0
    in02_high_ratio: float = 1.5
    in02_low_ratio: float = 0.5
    in02_min_days: int = 10
    in03_percentile: float = 90.0
    in03_min_days: int = 5
    in04_min_increase: int = 10
    in06_min_share: float = 0.25
    in06_min_total: int = 10
    in06_window_days: int = 90


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | str | None
    unit: str
    kind: str
    source: str


@dataclass(frozen=True)
class Insight:
    code: str
    severity: Severity
    text: str
    metrics: tuple[Metric, ...]
    sources: tuple[str, ...]
    rules_version: str = INSIGHT_RULES_VERSION


def fmt(value: float, decimals: int = 1) -> str:
    """Formato brasileiro, sem casas desnecessárias: 12.5 -> "12,5"; 30.0 -> "30"."""
    rounded = round(value, decimals)
    if rounded == int(rounded):
        return f"{int(rounded):,}".replace(",", ".")
    return f"{rounded:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


REANALYSIS = "Open-Meteo (reanálise ERA5/ERA5-Land)"
FORECAST = "Open-Meteo (previsão)"


def in01_heavy_forecast(
    *,
    region: str,
    forecast_24h_mm: float,
    p95_mm: float | None,
    month: int,
    t: Thresholds = DEFAULT_THRESHOLDS,
) -> Insight | None:
    """Chuva prevista em 24 h ≥ p95 das chuvas diárias do mês (1991–2020) no mesmo ponto."""
    if p95_mm is None or p95_mm <= 0 or forecast_24h_mm < p95_mm:
        return None
    name = MONTH_NAMES[month - 1]
    return Insight(
        code="IN-01",
        severity="atencao",
        text=(
            f"Chuva prevista de {fmt(forecast_24h_mm)} mm em 24 h na região {region}, acima de "
            f"{fmt(t.in01_percentile, 0)}% dos dias de {name} desde 1991 "
            f"(p{fmt(t.in01_percentile, 0)} = {fmt(p95_mm)} mm)."
        ),
        metrics=(
            Metric("Chuva prevista em 24 h", forecast_24h_mm, "mm", "FORECAST", FORECAST),
            Metric(
                f"p{fmt(t.in01_percentile, 0)} diário de {name} (1991–2020)",
                p95_mm,
                "mm",
                "MODELED",
                REANALYSIS,
            ),
        ),
        sources=(FORECAST, REANALYSIS),
    )


def in02_month_to_date(
    *,
    region: str,
    comparison: PeriodComparison | None,
    month: int,
    t: Thresholds = DEFAULT_THRESHOLDS,
) -> Insight | None:
    """Acumulado do mês até ontem ≥ 150% ou ≤ 50% da média do mesmo intervalo (reanálise)."""
    if comparison is None or comparison.ratio is None or comparison.days < t.in02_min_days:
        return None
    if t.in02_low_ratio < comparison.ratio < t.in02_high_ratio:
        return None
    name = MONTH_NAMES[month - 1]
    percent = comparison.ratio * 100
    return Insight(
        code="IN-02",
        severity="info",
        text=(
            f"{name.capitalize()} acumula {fmt(comparison.current)} mm até ontem na região "
            f"{region}, {fmt(percent, 0)}% da média para os mesmos {comparison.days} dias "
            f"(reanálise, {comparison.years_used} anos)."
        ),
        metrics=(
            Metric("Chuva do mês até ontem", comparison.current, "mm", "MODELED", REANALYSIS),
            Metric(
                f"Média dos mesmos dias (1991–2020, {comparison.years_used} anos)",
                comparison.reference,
                "mm",
                "MODELED",
                REANALYSIS,
            ),
            Metric("Razão", percent, "%", "DERIVED", "cálculo do sistema"),
        ),
        sources=(REANALYSIS,),
    )


def in03_dry_spell(
    *,
    region: str,
    current_days: int,
    historical_max_spells: Sequence[int],
    month: int,
    t: Thresholds = DEFAULT_THRESHOLDS,
) -> Insight | None:
    """Sequência seca atual ≥ p90 das maiores sequências secas do mês (1991–2020)."""
    if current_days < t.in03_min_days or len(historical_max_spells) < 25:
        return None
    limit = percentile(sorted(historical_max_spells), t.in03_percentile)
    if current_days < limit:
        return None
    name = MONTH_NAMES[month - 1]
    return Insight(
        code="IN-03",
        severity="info",
        text=(
            f"{current_days} dias seguidos sem chuva relevante na região {region}, sequência "
            f"maior que {fmt(t.in03_percentile, 0)}% das registradas em {name} desde 1991."
        ),
        metrics=(
            Metric("Dias seguidos com chuva < 1 mm", current_days, "dias", "MODELED", REANALYSIS),
            Metric(
                f"p{fmt(t.in03_percentile, 0)} da maior sequência seca de {name}",
                limit,
                "dias",
                "MODELED",
                REANALYSIS,
            ),
        ),
        sources=(REANALYSIS,),
    )


def in04_risk_increase(
    *, now_count: int, before_count: int | None, t: Thresholds = DEFAULT_THRESHOLDS
) -> Insight | None:
    """Setores alto + crítico aumentaram ≥ 10 em 24 h, ou passaram de 0 para ≥ 1."""
    if before_count is None:
        return None
    rose = now_count - before_count >= t.in04_min_increase
    appeared = before_count == 0 and now_count >= 1
    if not (rose or appeared):
        return None
    engine = "Motor de risco v0 (experimental)"
    return Insight(
        code="IN-04",
        severity="atencao",
        text=(
            "Setores com risco estimado alto ou crítico passaram de "
            f"{before_count} para {now_count} nas últimas 24 h (estimativa experimental)."
        ),
        metrics=(
            Metric("Setores alto + crítico agora", now_count, "setores", "DERIVED", engine),
            Metric("Setores alto + crítico há 24 h", before_count, "setores", "DERIVED", engine),
        ),
        sources=(engine,),
    )


FRESHNESS_TEXT = {
    "DELAYED": "atrasada",
    "STALE": "desatualizada",
    "UNAVAILABLE": "indisponível",
}


def in05_source_problem(
    *,
    source_name: str,
    freshness: str,
    reason: str,
    last_success_at: datetime | None,
) -> Insight | None:
    """Fonte atrasada, desatualizada ou com falha. Credencial ausente vira nota, não atenção."""
    if freshness not in FRESHNESS_TEXT:
        return None
    since = (
        f" (última coleta bem-sucedida em {last_success_at:%d/%m/%Y %H:%M} UTC)"
        if last_success_at
        else ""
    )
    credential = reason == "missing_credentials"
    text = (
        f"{source_name}: aguardando credencial de acesso."
        if credential
        else f"{source_name}: coleta {FRESHNESS_TEXT[freshness]}{since}."
    )
    return Insight(
        code="IN-05",
        severity="info" if credential else "atencao",
        text=text,
        metrics=(Metric("Frescor", freshness, "", "DERIVED", "estado das fontes"),),
        sources=("estado das fontes",),
    )


def in06_occurrence_concentration(
    *, counts_by_subprefecture: Mapping[str, int], t: Thresholds = DEFAULT_THRESHOLDS
) -> Insight | None:
    """Uma subprefeitura com ≥ 25% das ocorrências dos últimos 90 dias (mínimo 10 no total)."""
    total = sum(counts_by_subprefecture.values())
    if total < t.in06_min_total:
        return None
    name, count = max(counts_by_subprefecture.items(), key=lambda item: (item[1], item[0]))
    share = count / total
    if share < t.in06_min_share:
        return None
    source = "GeoSampa (Defesa Civil/SIGRC)"
    return Insight(
        code="IN-06",
        severity="info",
        text=(
            f"{name} concentra {fmt(share * 100, 0)}% das {total} ocorrências de alagamento e "
            f"inundação registradas nos últimos {t.in06_window_days} dias."
        ),
        metrics=(
            Metric(f"Ocorrências em {name}", count, "registros", "OBSERVED", source),
            Metric("Total de ocorrências", total, "registros", "OBSERVED", source),
        ),
        sources=(source,),
    )

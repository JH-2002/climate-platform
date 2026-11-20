"""Catálogo declarativo dos conjuntos de dados (FR-082, FR-094, BR-082).

As rotas e o Analytics Studio leem daqui: quais variáveis existem, em que unidade, que
agregações fazem sentido e que visualizações são compatíveis. Nada fica fixo na interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["OBSERVED", "MODELED", "FORECAST", "DERIVED"]
Agg = Literal["sum", "mean", "min", "max", "count"]
Grain = Literal["hour", "day", "week", "month", "year"]
Viz = Literal["line", "bar", "area", "histogram", "box", "calendar", "ranking", "table"]

GRAIN_ORDER: tuple[Grain, ...] = ("hour", "day", "week", "month", "year")


@dataclass(frozen=True)
class Variable:
    code: str
    label: str
    unit: str
    aggregations: tuple[Agg, ...]
    default_agg: Agg


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    description: str
    source_code: str  # data_sources.code
    kind: Kind
    resolution: Grain | Literal["event", "run"]
    spatial: str
    variables: tuple[Variable, ...]
    grains: tuple[Grain, ...]
    visualizations: tuple[Viz, ...]
    numeric: bool
    caveats: tuple[str, ...] = ()

    def variable(self, code: str) -> Variable | None:
        return next((v for v in self.variables if v.code == code), None)


_RAIN: tuple[Agg, ...] = ("sum", "mean", "min", "max", "count")
_TEMP: tuple[Agg, ...] = ("mean", "min", "max", "count")

DATASETS: dict[str, Dataset] = {
    d.id: d
    for d in (
        Dataset(
            id="iag-rain-monthly",
            name="Chuva mensal medida — IAG/USP (Água Funda)",
            description=(
                "Total mensal de chuva medido no pluviômetro da estação do IAG/USP, de 1933 a "
                "2025, publicado pela Prefeitura de São Paulo."
            ),
            source_code="iag-usp-rain-monthly",
            kind="OBSERVED",
            resolution="month",
            spatial="Uma estação (Água Funda, zona sul)",
            variables=(Variable("precipitation_month", "Chuva mensal", "mm", _RAIN, "sum"),),
            grains=("month", "year"),
            visualizations=("line", "bar", "histogram", "box", "table"),
            numeric=True,
            caveats=(
                "Representa a zona sul (Água Funda), não a cidade inteira.",
                "Atualização anual pela Prefeitura; o ano corrente ainda não está na série.",
            ),
        ),
        Dataset(
            id="reanalysis-daily",
            name="Reanálise diária — Open-Meteo (ERA5/ERA5-Land)",
            description=(
                "Chuva e temperaturas diárias estimadas por reanálise para os pontos da grade "
                "de previsão, de 1991 até ontem."
            ),
            source_code="open-meteo-archive",
            kind="MODELED",
            resolution="day",
            spatial="12 pontos da grade (chuva em células de ~25 km)",
            variables=(
                Variable("precipitation_sum", "Chuva diária", "mm", _RAIN, "sum"),
                Variable("air_temperature_max", "Temperatura máxima", "°C", _TEMP, "mean"),
                Variable("air_temperature_min", "Temperatura mínima", "°C", _TEMP, "mean"),
                Variable("air_temperature_mean", "Temperatura média", "°C", _TEMP, "mean"),
            ),
            grains=("day", "week", "month", "year"),
            visualizations=(
                "line",
                "bar",
                "area",
                "histogram",
                "box",
                "calendar",
                "ranking",
                "table",
            ),
            numeric=True,
            caveats=(
                "Estimativa de modelo, não medição.",
                "Subestima temporais locais; no centro, ~12% abaixo da normal medida do IAG/USP.",
                "Use para comparar um período com ele mesmo no mesmo ponto.",
            ),
        ),
        Dataset(
            id="forecast-hourly",
            name="Previsão horária — Open-Meteo",
            description="Previsão de 7 dias e estimativa das 72 h anteriores nos pontos da grade.",
            source_code="open-meteo-forecast",
            kind="FORECAST",
            resolution="hour",
            spatial="12 pontos da grade",
            variables=(
                Variable("precipitation", "Chuva", "mm", _RAIN, "sum"),
                Variable("air_temperature", "Temperatura", "°C", _TEMP, "mean"),
                Variable("relative_humidity", "Umidade relativa", "%", _TEMP, "mean"),
                Variable("wind_speed", "Vento", "m/s", _TEMP, "mean"),
            ),
            grains=("hour", "day"),
            visualizations=("line", "bar", "area", "table"),
            numeric=True,
            caveats=("Previsão de modelo: não é medição.",),
        ),
        Dataset(
            id="flood-occurrences",
            name="Ocorrências de alagamento e inundação — GeoSampa",
            description="Registros de atendimento da Defesa Civil (SIGRC) publicados no GeoSampa.",
            source_code="geosampa-flood-occurrences",
            kind="OBSERVED",
            resolution="event",
            spatial="Pontos; agrupáveis por subprefeitura",
            variables=(Variable("occurrences", "Ocorrências", "registros", ("count",), "count"),),
            grains=("day", "week", "month"),
            visualizations=("bar", "line", "ranking", "table"),
            numeric=False,
            caveats=(
                "Registros de atendimento: podem não incluir todos os eventos.",
                "O serviço WFS traz só o ano corrente.",
            ),
        ),
        Dataset(
            id="risk-assessments",
            name="Risco estimado — histórico das execuções",
            description="Categorias do motor de risco v0 (experimental) a cada execução horária.",
            source_code="flood-risk-engine",
            kind="DERIVED",
            resolution="run",
            spatial="793 setores de risco hidrológico",
            variables=(
                Variable("sectors", "Setores por categoria", "setores", ("count",), "count"),
            ),
            grains=("hour", "day"),
            visualizations=("line", "bar", "ranking", "table"),
            numeric=False,
            caveats=("Estimativa experimental do sistema: não é alerta oficial.",),
        ),
        Dataset(
            id="ingestion-runs",
            name="Coletas das fontes",
            description="Execuções de coleta de cada fonte: estado, duração e registros.",
            source_code="",
            kind="DERIVED",
            resolution="run",
            spatial="Por fonte",
            variables=(
                Variable("runs", "Execuções", "execuções", ("count",), "count"),
                Variable("duration_s", "Duração", "s", ("mean", "max", "count"), "mean"),
            ),
            grains=("hour", "day"),
            visualizations=("bar", "line", "table"),
            numeric=False,
        ),
    )
}


def aggregation_error(dataset: Dataset, variable_code: str, agg: str) -> str | None:
    variable = dataset.variable(variable_code)
    if variable is None:
        return f"variável desconhecida em {dataset.id}: {variable_code}"
    if agg not in variable.aggregations:
        if agg == "sum":
            label = variable.label.lower()
            return f"somar {label} não tem significado físico; use média, mínimo ou máximo"
        return f"agregação {agg} não disponível para {variable.label.lower()}"
    return None


def grain_error(dataset: Dataset, grain: str) -> str | None:
    if grain not in dataset.grains:
        options = ", ".join(dataset.grains)
        return f"{dataset.name}: agrupamento {grain} indisponível (use {options})"
    return None

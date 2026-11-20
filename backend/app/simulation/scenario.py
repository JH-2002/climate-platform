"""Cenário de chuva, faixas aceitas e cenários prontos (FR-100, FR-103, BR-104). Puro."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Pattern(StrEnum):
    """Distribuição da chuva no tempo."""

    CONSTANT = "CONSTANT"
    PEAKED = "PEAKED"
    SHARP = "SHARP"


PATTERN_LABELS = {
    Pattern.CONSTANT: "constante",
    Pattern.PEAKED: "concentrada (50% na hora de pico)",
    Pattern.SHARP: "muito concentrada (70% na hora de pico)",
}
# Fração do total que cai na hora de pico. Constante: total ÷ duração.
PEAK_SHARE = {Pattern.CONSTANT: 0.0, Pattern.PEAKED: 0.5, Pattern.SHARP: 0.7}

TOTAL_MM = (1.0, 300.0)
DURATION_H = (1, 24)
RADIUS_KM = (2.0, 30.0)
ANTECEDENT_MM = (0.0, 300.0)
# Região de interesse (ADR-002), com folga: o centro da célula precisa estar na cidade.
LAT_RANGE = (-24.1, -23.3)
LON_RANGE = (-46.9, -46.3)


class ScenarioError(ValueError):
    """Cenário fora das faixas aceitas (BR-104). A mensagem vai para o usuário."""


@dataclass(frozen=True)
class Cell:
    """Célula de chuva: 100% até o raio, caindo em linha reta até 0% em duas vezes o raio."""

    latitude: float
    longitude: float
    radius_km: float


@dataclass(frozen=True)
class Scenario:
    total_mm: float
    duration_h: int
    pattern: Pattern
    antecedent_mm: float
    cell: Cell | None = None  # None = cidade inteira

    def as_dict(self) -> dict[str, object]:
        return {
            "total_mm": self.total_mm,
            "duration_h": self.duration_h,
            "pattern": self.pattern.value,
            "antecedent_mm": self.antecedent_mm,
            "cell": None
            if self.cell is None
            else {
                "latitude": self.cell.latitude,
                "longitude": self.cell.longitude,
                "radius_km": self.cell.radius_km,
            },
        }


def _check(name: str, value: float, limits: tuple[float, float], unit: str) -> None:
    low, high = limits
    if not low <= value <= high:
        raise ScenarioError(
            f"{name} deve ficar entre {low:g} e {high:g} {unit} (recebido: {value:g} {unit})"
        )


def validate(scenario: Scenario) -> None:
    _check("Chuva total", scenario.total_mm, TOTAL_MM, "mm")
    _check("Duração", scenario.duration_h, (float(DURATION_H[0]), float(DURATION_H[1])), "h")
    _check("Chuva das 72 h anteriores", scenario.antecedent_mm, ANTECEDENT_MM, "mm")
    if scenario.cell is not None:
        _check("Raio da célula", scenario.cell.radius_km, RADIUS_KM, "km")
        _check("Latitude do centro", scenario.cell.latitude, LAT_RANGE, "°")
        _check("Longitude do centro", scenario.cell.longitude, LON_RANGE, "°")


@dataclass(frozen=True)
class Preset:
    code: str
    name: str
    description: str
    origin: str
    scenario: Scenario


# Centro padrão das células: Praça da Sé. O usuário pode mover.
DEFAULT_CENTER = (-23.5505, -46.6333)

PRESETS: tuple[Preset, ...] = (
    Preset(
        code="pancada-de-verao",
        name="Pancada de verão",
        description="40 mm em 1 h numa célula de 6 km.",
        origin="Faixa “forte” de 1 h do motor de risco (25 a 50 mm/h).",
        scenario=Scenario(40.0, 1, Pattern.CONSTANT, 0.0, Cell(*DEFAULT_CENTER, 6.0)),
    ),
    Preset(
        code="chuva-persistente",
        name="Chuva persistente",
        description="80 mm em 12 h, constante, na cidade inteira, com 30 mm nas 72 h anteriores.",
        origin="Faixa “forte” de 24 h do motor de risco (60 a 100 mm).",
        scenario=Scenario(80.0, 12, Pattern.CONSTANT, 30.0),
    ),
    Preset(
        code="solo-encharcado",
        name="Solo encharcado",
        description="30 mm em 3 h na cidade inteira, depois de 100 mm nas 72 h anteriores.",
        origin="Gatilho de chuva antecedente do motor de risco (50 mm ou mais em 72 h).",
        scenario=Scenario(30.0, 3, Pattern.CONSTANT, 100.0),
    ),
    Preset(
        code="extremo-de-referencia",
        name="Extremo de referência",
        description="136 mm em 24 h, concentrada, na cidade inteira.",
        origin=(
            "Maior chuva diária da reanálise ERA5 no centro desde 1991 (25/02/2010). "
            "A reanálise subestima temporais: medições locais podem ser maiores."
        ),
        scenario=Scenario(136.0, 24, Pattern.PEAKED, 0.0),
    ),
)

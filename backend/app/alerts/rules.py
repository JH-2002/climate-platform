"""Regras dos alertas do sistema (spec 009, FR-144). Funções puras, sem banco (NFR-143).

As regras recebem um retrato do estado e os alertas abertos, e devolvem as ações a aplicar.
Elas tratam só da **estimativa experimental** e da **saúde dos dados**: nunca de alerta oficial
(Constituição §1) e nunca de simulação (BR-143).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from app.alerts.status import display_name

RULES_VERSION = "1"

RISK_RULE = "risk-subprefecture"
SOURCE_RULE = "source-unavailable"
STALE_RULE = "risk-stale"

Category = Literal["RISK_ESTIMATE", "DATA_QUALITY"]
Level = Literal["HIGH", "CRITICAL", "WARNING"]
ActionKind = Literal["open", "update", "miss", "close"]

# Fontes sem as quais um alerta pode deixar de chegar (BR-144, US-094).
WATCHED_SOURCES: dict[str, str] = {
    "idap-alerts": "alertas da Defesa Civil (IDAP)",
    "inmet-warnings": "avisos do INMET",
    "open-meteo-forecast": "previsão da Open-Meteo",
}
_BAD_FRESHNESS = ("STALE", "UNAVAILABLE")


@dataclass(frozen=True)
class Thresholds:
    risk_stale_hours: float = 3.0
    clear_after: int = 2


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class SubprefectureRisk:
    name: str
    high: int
    critical: int


@dataclass(frozen=True)
class SourceState:
    code: str
    freshness: str
    last_success_at: datetime | None


@dataclass(frozen=True)
class Snapshot:
    now: datetime
    risk_computed_at: datetime | None
    subprefectures: Sequence[SubprefectureRisk] = ()
    sources: Sequence[SourceState] = ()


@dataclass(frozen=True)
class Condition:
    rule_code: str
    scope_key: str
    scope_label: str
    category: Category
    level: Level
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenAlert:
    id: int
    rule_code: str
    scope_key: str
    level: str
    message: str
    clear_count: int


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    condition: Condition | None = None
    alert_id: int | None = None
    clear_count: int = 0


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _risk_conditions(snapshot: Snapshot) -> list[Condition]:
    conditions: list[Condition] = []
    for sp in snapshot.subprefectures:
        if sp.high <= 0 and sp.critical <= 0:
            continue
        level: Level = "CRITICAL" if sp.critical > 0 else "HIGH"
        parts = []
        if sp.critical:
            parts.append(f"{_plural(sp.critical, 'setor', 'setores')} em crítico")
        if sp.high:
            parts.append(f"{_plural(sp.high, 'setor', 'setores')} em alto")
        conditions.append(
            Condition(
                rule_code=RISK_RULE,
                scope_key=sp.name,
                scope_label=display_name(sp.name),
                category="RISK_ESTIMATE",
                level=level,
                title=f"Estimativa do sistema: risco {'crítico' if level == 'CRITICAL' else 'alto'}"
                f" em {display_name(sp.name)}",
                message=" e ".join(parts)
                + " na estimativa mais recente. Estimativa experimental, não é alerta oficial.",
                details={"high": sp.high, "critical": sp.critical},
            )
        )
    return conditions


def _source_conditions(snapshot: Snapshot) -> list[Condition]:
    conditions: list[Condition] = []
    for source in snapshot.sources:
        label = WATCHED_SOURCES.get(source.code)
        if label is None or source.freshness not in _BAD_FRESHNESS:
            continue
        state = "atrasada" if source.freshness == "STALE" else "indisponível"
        conditions.append(
            Condition(
                rule_code=SOURCE_RULE,
                scope_key=source.code,
                scope_label=label,
                category="DATA_QUALITY",
                level="WARNING",
                title=f"Fonte {state}: {label}",
                message=f"A coleta de {label} está {state}. O que depende dela pode estar "
                "incompleto até a próxima coleta com sucesso.",
                details={
                    "freshness": source.freshness,
                    "last_success_at": source.last_success_at.isoformat()
                    if source.last_success_at
                    else None,
                },
            )
        )
    return conditions


def _stale_condition(snapshot: Snapshot, t: Thresholds) -> list[Condition]:
    computed = snapshot.risk_computed_at
    if computed is not None and snapshot.now - computed <= timedelta(hours=t.risk_stale_hours):
        return []
    hours = f"{t.risk_stale_hours:g}".replace(".", ",")
    return [
        Condition(
            rule_code=STALE_RULE,
            scope_key="city",
            scope_label="Cidade",
            category="DATA_QUALITY",
            level="WARNING",
            title="Risco estimado sem atualização",
            message=f"O risco estimado não é recalculado há mais de {hours} h. "
            "As cores de risco podem não refletir a previsão atual.",
            details={"last_computed_at": computed.isoformat() if computed else None},
        )
    ]


def evaluate(snapshot: Snapshot, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> list[Condition]:
    """Condições que valem agora, uma por regra e escopo."""
    return [
        *_risk_conditions(snapshot),
        *_source_conditions(snapshot),
        *_stale_condition(snapshot, thresholds),
    ]


def plan_actions(
    conditions: Sequence[Condition],
    open_alerts: Sequence[OpenAlert],
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> list[Action]:
    """Abre o que é novo, atualiza o que mudou e encerra com histerese (FR-144).

    - Condição nova: abre.
    - Condição que continua: atualiza se o nível ou a mensagem mudaram, ou se havia uma
      ausência contada (zera a contagem).
    - Alerta aberto sem condição: conta a ausência; encerra na `clear_after`-ésima seguida.
    """
    by_key = {(a.rule_code, a.scope_key): a for a in open_alerts}
    actions: list[Action] = []
    seen: set[tuple[str, str]] = set()
    for condition in conditions:
        key = (condition.rule_code, condition.scope_key)
        if key in seen:
            continue
        seen.add(key)
        current = by_key.get(key)
        if current is None:
            actions.append(Action("open", condition))
        elif (
            current.level != condition.level
            or current.message != condition.message
            or current.clear_count > 0
        ):
            actions.append(Action("update", condition, current.id))
    for key, alert in by_key.items():
        if key in seen:
            continue
        count = alert.clear_count + 1
        kind: ActionKind = "close" if count >= thresholds.clear_after else "miss"
        actions.append(Action(kind, None, alert.id, count))
    return actions

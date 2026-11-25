"""Spec 009 — regras dos alertas do sistema e estado dos alertas oficiais (puros)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.alerts.rules import (
    RISK_RULE,
    SOURCE_RULE,
    STALE_RULE,
    OpenAlert,
    Snapshot,
    SourceState,
    SubprefectureRisk,
    Thresholds,
    evaluate,
    plan_actions,
)
from app.alerts.status import display_name, official_status, severity_label

NOW = datetime(2026, 11, 24, 20, 0, tzinfo=UTC)


def snapshot(**kw: object) -> Snapshot:
    base: dict[str, object] = {"now": NOW, "risk_computed_at": NOW - timedelta(minutes=30)}
    base.update(kw)
    return Snapshot(**base)  # type: ignore[arg-type]


def test_risk_rule_one_alert_per_subprefecture_with_highest_level() -> None:
    conditions = evaluate(
        snapshot(
            subprefectures=[
                SubprefectureRisk("PENHA", high=2, critical=1),
                SubprefectureRisk("SE", high=1, critical=0),
                SubprefectureRisk("LAPA", high=0, critical=0),
            ]
        )
    )
    risk = {c.scope_key: c for c in conditions if c.rule_code == RISK_RULE}
    assert set(risk) == {"PENHA", "SE"}
    assert risk["PENHA"].level == "CRITICAL" and risk["SE"].level == "HIGH"
    assert risk["PENHA"].category == "RISK_ESTIMATE"
    assert "1 setor em crítico e 2 setores em alto" in risk["PENHA"].message
    assert "não é alerta oficial" in risk["SE"].message
    assert risk["SE"].title == "Estimativa do sistema: risco alto em Sé"


def test_source_rule_only_for_watched_sources_that_are_stale_or_unavailable() -> None:
    conditions = evaluate(
        snapshot(
            sources=[
                SourceState("idap-alerts", "STALE", NOW - timedelta(hours=1)),
                SourceState("inmet-warnings", "UNAVAILABLE", None),
                SourceState("open-meteo-forecast", "DELAYED", NOW),
                SourceState("geosampa-basins", "STALE", None),
            ]
        )
    )
    sources = {c.scope_key: c for c in conditions if c.rule_code == SOURCE_RULE}
    assert set(sources) == {"idap-alerts", "inmet-warnings"}
    assert sources["idap-alerts"].title.startswith("Fonte atrasada")
    assert sources["inmet-warnings"].title.startswith("Fonte indisponível")
    assert all(c.category == "DATA_QUALITY" for c in sources.values())


def test_stale_rule() -> None:
    assert not [c for c in evaluate(snapshot()) if c.rule_code == STALE_RULE]
    old = evaluate(snapshot(risk_computed_at=NOW - timedelta(hours=4)))
    assert [c.rule_code for c in old] == [STALE_RULE]
    never = evaluate(snapshot(risk_computed_at=None))
    assert never[0].details == {"last_computed_at": None}
    custom = evaluate(snapshot(risk_computed_at=NOW - timedelta(hours=2)), Thresholds(1.5))
    assert "1,5 h" in custom[0].message


def _open(condition_rule: str, scope: str, level: str, message: str, misses: int = 0) -> OpenAlert:
    return OpenAlert(1, condition_rule, scope, level, message, misses)


def test_plan_opens_updates_and_closes_with_hysteresis() -> None:
    """AC-143: um alerta por escopo; fecha só na segunda avaliação seguida sem a condição."""
    (condition,) = evaluate(snapshot(subprefectures=[SubprefectureRisk("PENHA", 1, 0)]))
    assert [a.kind for a in plan_actions([condition], [])] == ["open"]
    same = _open(RISK_RULE, "PENHA", condition.level, condition.message)
    assert plan_actions([condition], [same]) == []  # nada muda: nenhuma ação
    changed = _open(RISK_RULE, "PENHA", "CRITICAL", "outra")
    assert [a.kind for a in plan_actions([condition], [changed])] == ["update"]
    first_miss = plan_actions([], [same])
    assert [(a.kind, a.clear_count) for a in first_miss] == [("miss", 1)]
    second = _open(RISK_RULE, "PENHA", condition.level, condition.message, misses=1)
    assert [(a.kind, a.clear_count) for a in plan_actions([], [second])] == [("close", 2)]
    # a condição volta depois de uma ausência: atualiza e zera a contagem
    assert [a.kind for a in plan_actions([condition], [second])] == ["update"]


def test_duplicate_conditions_open_once() -> None:
    (condition,) = evaluate(snapshot(subprefectures=[SubprefectureRisk("PENHA", 1, 0)]))
    assert len(plan_actions([condition, condition], [])) == 1


def test_official_status() -> None:
    onset, expires = NOW - timedelta(hours=1), NOW + timedelta(hours=1)
    assert official_status(NOW, onset, expires, None) == "ACTIVE"
    assert official_status(NOW, NOW + timedelta(hours=2), None, None) == "UPCOMING"
    assert official_status(NOW, onset, NOW, None) == "EXPIRED"
    assert official_status(NOW, onset, expires, "CANCELLED") == "CANCELLED"
    assert official_status(NOW, onset, expires, "SUPERSEDED") == "SUPERSEDED"
    assert severity_label("Severe") == "Severa" and severity_label(None) == "Desconhecida"


def test_display_name() -> None:
    assert display_name("CASA VERDE-CACHOEIRINHA") == "Casa Verde-Cachoeirinha"
    assert display_name("CIDADE DE DEUS") == "Cidade de Deus"
    assert display_name("M BOI MIRIM") == "M'Boi Mirim"

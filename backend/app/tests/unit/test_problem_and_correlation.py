"""FR-004 / FR-005 — utilitários puros."""

from __future__ import annotations

import pytest

from app.core.correlation import resolve_correlation_id
from app.core.problem import build_problem


def test_problem_has_rfc9457_members_and_correlation_id() -> None:
    problem = build_problem(status=404, instance="/x", correlation_id="abc")
    assert problem == {
        "type": "about:blank",
        "title": "Recurso não encontrado",
        "status": 404,
        "instance": "/x",
        "correlation_id": "abc",
    }


def test_problem_extensions_cannot_override_reserved_members() -> None:
    with pytest.raises(ValueError, match="reservados"):
        build_problem(status=400, extensions={"status": 200})


def test_problem_unknown_status_has_generic_title() -> None:
    assert build_problem(status=599)["title"] == "Erro"


def test_valid_incoming_correlation_id_is_kept() -> None:
    assert resolve_correlation_id("abc-123_X.y") == "abc-123_X.y"


@pytest.mark.parametrize("bad", [None, "", "a b", "x" * 129, "id\nlinha-forjada", "<script>"])
def test_unsafe_correlation_id_is_replaced(bad: str | None) -> None:
    generated = resolve_correlation_id(bad)
    assert generated != bad
    assert len(generated) == 32

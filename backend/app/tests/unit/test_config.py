"""FR-012 / AC-007 — validação das configurações na inicialização."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("pydantic_settings")

from app.core.config import load_settings


def test_missing_database_url_exits_with_clear_log(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        load_settings()
    assert exc_info.value.code == 1
    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert record["event"] == "missing_required_setting"
    assert "DATABASE_URL" in record["settings"]


def test_wrong_database_scheme_is_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@db/x")
    with pytest.raises(SystemExit):
        load_settings()
    err = capsys.readouterr().err
    assert "invalid_setting" in err
    assert "pw@" not in err  # o valor em si nunca é exibido


def test_valid_environment_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INMET_TOKEN", "abc")
    settings = load_settings()
    assert settings.app_env == "test"
    assert settings.inmet_token is not None
    assert "abc" not in repr(settings)

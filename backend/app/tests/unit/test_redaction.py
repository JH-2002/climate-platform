"""Constituição §5 — nenhum segredo nos logs."""

from __future__ import annotations

from app.core.redaction import REDACTED, redact_event


def test_sensitive_keys_are_redacted() -> None:
    event = redact_event(
        None, "info", {"event": "x", "inmet_token": "abc", "Authorization": "Bearer y"}
    )
    assert event["inmet_token"] == REDACTED
    assert event["Authorization"] == REDACTED
    assert event["event"] == "x"


def test_password_in_url_is_masked() -> None:
    event = redact_event(None, "info", {"dsn": "postgresql+asyncpg://climate:s3cret@db:5432/c"})
    assert event["dsn"] == f"postgresql+asyncpg://climate:{REDACTED}@db:5432/c"


def test_nested_mappings_are_redacted() -> None:
    event = redact_event(None, "info", {"source": {"name": "inmet", "api_key": "k"}})
    assert event["source"] == {"name": "inmet", "api_key": REDACTED}

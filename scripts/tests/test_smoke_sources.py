"""Testes das partes puras de scripts/smoke_sources.py (T014)."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import smoke_sources as smoke  # noqa: E402


def test_token_is_masked_everywhere() -> None:
    endpoints = smoke.build_endpoints(date(2026, 11, 19), "SECRET123")
    token_ep = next(e for e in endpoints if e.secret)
    result = smoke.Result(token_ep, 200, 10.0, 5, "ok SECRET123")
    md = smoke.render_markdown([result], datetime(2026, 11, 19, tzinfo=UTC), True)
    assert "SECRET123" not in md
    assert "/token/estacao/2026-11-18/2026-11-19/A701/***" in md


def test_without_token_no_token_route_is_probed() -> None:
    endpoints = smoke.build_endpoints(date(2026, 11, 19), None)
    assert not any("/token/" in e.url for e in endpoints)


def test_summarize_json_list() -> None:
    body = b'[{"CD_ESTACAO": "A701", "DC_NOME": "SAO PAULO"}, {"CD_ESTACAO": "A702"}]'
    assert smoke.summarize_payload(body, "application/json") == (
        "lista com 2 itens; campos do 1º: CD_ESTACAO, DC_NOME"
    )


def test_summarize_json_object_and_edge_cases() -> None:
    assert smoke.summarize_payload(b'{"hourly": {}, "latitude": 1}', "application/json") == (
        "objeto JSON; chaves: hourly, latitude"
    )
    assert smoke.summarize_payload(b"", "application/json") == "corpo vazio"
    assert smoke.summarize_payload(b"[]", "application/json") == "lista JSON vazia"
    assert smoke.summarize_payload(b"{oops", "application/json").startswith("JSON inválido")
    html = smoke.summarize_payload(b"<html></html>", "text/html; charset=utf-8")
    assert html == "HTML (13 bytes)"


def test_markdown_escapes_pipes_and_shows_failures() -> None:
    ep = smoke.Endpoint("X", "y", "https://example.org")
    result = smoke.Result(ep, None, None, 0, "falha | conexão")
    md = smoke.render_markdown([result], datetime(2026, 1, 1, tzinfo=UTC), False)
    assert "| X | y | — | — | 0 | falha / conexão |" in md

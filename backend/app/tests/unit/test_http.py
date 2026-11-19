"""T011 — busca HTTP com retentativas (NFR-020)."""

from __future__ import annotations

import asyncio
import random

import pytest

pytest.importorskip("httpx")

import httpx

from app.integrations.http import SourceHTTPError, backoff_delay, fetch


def _client(responses: list[object]) -> tuple[object, list[str]]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, httpx.Response)
        return item

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def _no_sleep(_: float) -> None:
    return None


def _run(responses: list[object], **kwargs: object) -> tuple[object, list[str]]:
    client, calls = _client(responses)

    async def go() -> object:
        async with client:  # type: ignore[attr-defined]
            return await fetch(client, "https://exemplo.test/x", sleep=_no_sleep, **kwargs)  # type: ignore[arg-type]

    try:
        return asyncio.run(go()), calls
    except SourceHTTPError as exc:
        return exc, calls


def test_success_on_first_try() -> None:
    result, calls = _run([httpx.Response(200, json=[1])])
    assert result.status == 200  # type: ignore[attr-defined]
    assert len(calls) == 1


def test_retries_5xx_then_succeeds() -> None:
    result, calls = _run([httpx.Response(503), httpx.Response(502), httpx.Response(200, json={})])
    assert result.status == 200  # type: ignore[attr-defined]
    assert len(calls) == 3


def test_retries_network_errors_and_gives_up() -> None:
    result, calls = _run([httpx.ConnectError("boom")])
    assert isinstance(result, SourceHTTPError)
    assert result.status is None
    assert "ConnectError" in str(result)
    assert len(calls) == 3


def test_does_not_retry_client_errors() -> None:
    result, calls = _run([httpx.Response(404)])
    assert isinstance(result, SourceHTTPError)
    assert result.status == 404
    assert len(calls) == 1


def test_204_is_an_empty_result() -> None:
    result, _ = _run([httpx.Response(204)])
    assert result.is_empty  # type: ignore[attr-defined]


def test_backoff_grows_exponentially_with_bounded_jitter() -> None:
    rng = random.Random(1)
    delays = [backoff_delay(n, 1.0, rng) for n in (1, 2, 3)]
    for attempt, delay in zip((1, 2, 3), delays, strict=True):
        base = 2 ** (attempt - 1)
        assert base <= delay <= base * 1.5

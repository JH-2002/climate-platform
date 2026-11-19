"""Smoke test das fontes de dados externas (FR-011 / T014).

Usa só a biblioteca padrão, então roda em qualquer Python >= 3.11 sem instalar nada:

    python scripts/smoke_sources.py                 # gera docs/data-sources/smoke-results.md
    $env:INMET_TOKEN="..."  (PowerShell)  para testar também a rota com token

O token nunca é gravado na saída (fica mascarado nas URLs).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

USER_AGENT = "climate-platform-smoke/0.1 (projeto de portfolio; contato pelo repositorio)"
TIMEOUT_S = 20
SAMPLE_STATION = "A701"  # INMET São Paulo — Mirante de Santana
SAO_PAULO = (-23.55, -46.63)
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "data-sources" / "smoke-results.md"


@dataclass(frozen=True)
class Endpoint:
    source: str
    purpose: str
    url: str
    secret: str | None = None


@dataclass(frozen=True)
class Result:
    endpoint: Endpoint
    status: int | None
    latency_ms: float | None
    size_bytes: int
    summary: str


def mask_secret(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "***")


def summarize_payload(body: bytes, content_type: str) -> str:
    """Descrição curta e legível do corpo da resposta (sem despejar o conteúdo)."""
    if not body:
        return "corpo vazio"
    if "json" in content_type or body[:1] in (b"{", b"["):
        try:
            data = json.loads(body)
        except ValueError:
            return f"JSON inválido ({len(body)} bytes)"
        if isinstance(data, list):
            if not data:
                return "lista JSON vazia"
            first = data[0]
            if isinstance(first, dict):
                keys = ", ".join(sorted(first)[:12])
            else:
                keys = type(first).__name__
            return f"lista com {len(data)} itens; campos do 1º: {keys}"
        if isinstance(data, dict):
            return "objeto JSON; chaves: " + ", ".join(sorted(data)[:12])
        return f"JSON {type(data).__name__}"
    if "html" in content_type:
        return f"HTML ({len(body)} bytes)"
    return f"{content_type or 'conteúdo'} ({len(body)} bytes)"


def build_endpoints(today: date, inmet_token: str | None) -> list[Endpoint]:
    start = (today - timedelta(days=1)).isoformat()
    end = today.isoformat()
    lat, lon = SAO_PAULO
    endpoints = [
        Endpoint(
            "INMET",
            "Lista de estações automáticas (sem token)",
            "https://apitempo.inmet.gov.br/estacoes/T",
        ),
        Endpoint(
            "INMET",
            "Dados horários — rota antiga sem token (relatos de 404 em 2026)",
            f"https://apitempo.inmet.gov.br/estacao/{start}/{end}/{SAMPLE_STATION}",
        ),
        Endpoint(
            "Open-Meteo",
            "Previsão 7 dias, São Paulo",
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m"
            "&forecast_days=7&timezone=UTC",
        ),
        Endpoint(
            "Copernicus DEM",
            "Catálogo STAC GLO-30 (AWS Open Data)",
            "https://copernicus-dem-30m-stac.s3.amazonaws.com/",
        ),
        Endpoint(
            "ANA",
            "HidroWebService (Swagger)",
            "https://www.ana.gov.br/hidrowebservice/swagger-ui/index.html",
        ),
    ]
    if inmet_token:
        endpoints.insert(
            2,
            Endpoint(
                "INMET",
                "Dados horários com token",
                "https://apitempo.inmet.gov.br/token/estacao/"
                f"{start}/{end}/{SAMPLE_STATION}/{inmet_token}",
                secret=inmet_token,
            ),
        )
    return endpoints


def probe(endpoint: Endpoint) -> Result:
    request = urllib.request.Request(endpoint.url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read() or b""
        status = exc.code
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return Result(endpoint, None, None, 0, f"falha de conexão: {type(reason).__name__}")
    latency = round((time.perf_counter() - start) * 1000, 1)
    summary = mask_secret(summarize_payload(body, content_type), endpoint.secret)
    return Result(endpoint, status, latency, len(body), summary)


def render_markdown(results: list[Result], generated_at: datetime, inmet_token_set: bool) -> str:
    lines = [
        "# Smoke test das fontes externas",
        "",
        f"> Gerado em {generated_at.isoformat(timespec='seconds')} (UTC) por "
        "`scripts/smoke_sources.py`.",
        f"> INMET_TOKEN definido: {'sim' if inmet_token_set else 'não'}.",
        "> Resultado de um único momento: indica acesso, não disponibilidade contínua.",
        "",
        "| Fonte | Finalidade | HTTP | Latência (ms) | Tamanho | Resumo | URL |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        url = mask_secret(r.endpoint.url, r.endpoint.secret)
        summary = mask_secret(r.summary, r.endpoint.secret).replace("|", "/")
        lines.append(
            f"| {r.endpoint.source} | {r.endpoint.purpose} | {r.status if r.status else '—'} "
            f"| {r.latency_ms if r.latency_ms is not None else '—'} | {r.size_bytes} "
            f"| {summary} | `{url}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    token = os.environ.get("INMET_TOKEN") or None
    now = datetime.now(UTC)
    results = [probe(e) for e in build_endpoints(now.date(), token)]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_markdown(results, now, token is not None), encoding="utf-8")
    for r in results:
        print(f"[{r.status or 'ERRO'}] {r.endpoint.source}: {r.endpoint.purpose} — {r.summary}")
    print(f"\nRelatório: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

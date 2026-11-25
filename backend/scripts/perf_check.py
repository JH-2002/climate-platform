"""Metas de desempenho da API (spec 011, FR-180). Só biblioteca padrão.

Uso, com a pilha rodando (dentro do contêiner da API, para medir sem a rede da máquina):
    docker compose exec backend python scripts/perf_check.py
    docker compose exec backend python scripts/perf_check.py --base http://localhost:8000 -n 40

Mede p50 e p95 de cada rota em requisições sequenciais e compara com a meta. O total fica abaixo
do limite geral de requisições por minuto (240). Código de saída 1 se alguma meta falhar.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import urllib.error
import urllib.request

# rota -> meta de p95 em ms (FR-180)
BUDGETS: dict[str, float] = {
    "/api/v1/alerts/active": 200,
    "/api/v1/risk/summary": 300,
    "/api/v1/map/layers/risk": 800,
    "/api/v1/weather/current": 300,
    "/api/v1/geo/basins": 500,
}


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    rank = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[rank]


def measure(url: str, n: int) -> tuple[list[float], int]:
    times: list[float] = []
    errors = 0
    for _ in range(n):
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 — só http(s)
                response.read()
                if response.status != 200:
                    errors += 1
        except (urllib.error.URLError, TimeoutError):
            errors += 1
            continue
        times.append((time.perf_counter() - start) * 1000)
    return times, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("-n", type=int, default=40, help="requisições por rota (padrão 40)")
    args = parser.parse_args(argv)
    if not args.base.startswith(("http://", "https://")):
        parser.error("--base precisa começar com http:// ou https://")
    ok = True
    print(f"{'rota':32} {'p50 (ms)':>9} {'p95 (ms)':>9} {'meta':>7}  resultado")
    for path, budget in BUDGETS.items():
        # a primeira chamada aquece conexões e caches; não entra na conta
        measure(args.base + path, 1)
        times, errors = measure(args.base + path, args.n)
        p50, p95 = statistics.median(times) if times else float("nan"), percentile(times, 95)
        passed = errors == 0 and p95 <= budget
        ok &= passed
        verdict = "ok" if passed else ("FALHOU" if errors == 0 else f"FALHOU ({errors} erros)")
        print(f"{path:32} {p50:9.1f} {p95:9.1f} {budget:7.0f}  {verdict}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

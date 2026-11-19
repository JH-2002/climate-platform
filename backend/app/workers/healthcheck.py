"""Healthchecks dos containers: `python -m app.workers.healthcheck {api|worker|beat}`.

Código de saída 0 = saudável, 1 = com problema. Usa apenas o que cada container já possui.
"""

from __future__ import annotations

import socket
import sys
import urllib.request
from datetime import UTC, datetime
from typing import cast

BEAT_MAX_AGE_S = 120
API_HEALTH_URL = "http://localhost:8000/api/v1/health"


def heartbeat_is_fresh(raw: bytes | str | None, now: datetime, max_age_s: int) -> bool:
    if raw is None:
        return False
    value = raw.decode() if isinstance(raw, bytes) else raw
    try:
        last = datetime.fromisoformat(value)
    except ValueError:
        return False
    if last.tzinfo is None:
        return False
    return 0 <= (now - last).total_seconds() <= max_age_s


def check_api() -> bool:
    try:
        with urllib.request.urlopen(API_HEALTH_URL, timeout=3) as resp:  # noqa: S310
            return bool(resp.status == 200)
    except OSError:
        return False


def check_worker() -> bool:
    from app.workers.celery_app import celery_app

    replies = celery_app.control.ping(destination=[f"celery@{socket.gethostname()}"], timeout=5)
    return bool(replies)


def check_beat() -> bool:
    import redis

    from app.core.config import get_settings
    from app.workers.celery_app import HEARTBEAT_KEY

    client = redis.Redis.from_url(get_settings().redis_url, socket_timeout=3)
    try:
        raw = cast("bytes | None", client.get(HEARTBEAT_KEY))
    finally:
        client.close()
    return heartbeat_is_fresh(raw, datetime.now(UTC), BEAT_MAX_AGE_S)


CHECKS = {"api": check_api, "worker": check_worker, "beat": check_beat}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in CHECKS:
        print(f"uso: python -m app.workers.healthcheck {{{'|'.join(CHECKS)}}}", file=sys.stderr)
        return 2
    try:
        return 0 if CHECKS[argv[1]]() else 1
    except Exception as exc:  # o healthcheck nunca deve terminar só com um traceback
        print(f"healthcheck {argv[1]} falhou: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

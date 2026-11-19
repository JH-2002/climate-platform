"""Inspeção dos workers usada na verificação de prontidão da API."""

from __future__ import annotations

import asyncio

from app.core.health import CheckFn


class WorkerUnavailableError(RuntimeError):
    pass


def make_worker_ping(timeout_s: float) -> CheckFn:
    """Faz ping nos workers Celery pelo broker sem bloquear o event loop."""

    async def ping_workers() -> dict[str, str]:
        from app.workers.celery_app import celery_app

        replies = await asyncio.to_thread(celery_app.control.ping, timeout=timeout_s)
        if not replies:
            raise WorkerUnavailableError
        return {"workers ativos": str(len(replies))}

    return ping_workers

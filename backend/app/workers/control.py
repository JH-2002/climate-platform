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

        # limit=1: retorna assim que o primeiro worker responde, sem esperar o timeout todo.
        replies = await asyncio.to_thread(celery_app.control.ping, timeout=timeout_s, limit=1)
        if not replies:
            raise WorkerUnavailableError
        return {"worker": next(iter(replies[0]))}

    return ping_workers

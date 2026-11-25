"""Envio de tarefas ao Celery a partir da API, sem bloquear o event loop (spec 010)."""

from __future__ import annotations

import asyncio
from typing import Any


async def send_task(name: str, *args: Any) -> None:
    from app.workers.celery_app import celery_app

    await asyncio.to_thread(celery_app.send_task, name, args=list(args))

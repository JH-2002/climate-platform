"""Middleware ASGI: correlation ID, log de requisições e resposta 500 de último recurso."""

from __future__ import annotations

import json
import time

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.correlation import HEADER_NAME, correlation_id_var, resolve_correlation_id
from app.core.problem import PROBLEM_MEDIA_TYPE, build_problem

logger = structlog.get_logger("app.request")


class CorrelationIdMiddleware:
    """ASGI puro (sem BaseHTTPMiddleware) para que as contextvars cheguem aos handlers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = resolve_correlation_id(Headers(scope=scope).get(HEADER_NAME))
        token = correlation_id_var.set(correlation_id)
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        status_code = 500
        response_started = False
        start = time.perf_counter()

        async def send_with_header(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message).append(HEADER_NAME, correlation_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        except Exception:
            logger.exception("unhandled_exception", path=scope.get("path"))
            if response_started:
                raise
            await self._send_internal_error(send_with_header, scope, correlation_id)
        finally:
            logger.info(
                "request_completed",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_code,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            structlog.contextvars.unbind_contextvars("correlation_id")
            correlation_id_var.reset(token)

    @staticmethod
    async def _send_internal_error(send: Send, scope: Scope, correlation_id: str) -> None:
        body = json.dumps(
            build_problem(
                status=500,
                detail="Erro interno inesperado. Use o correlation_id para rastrear o problema.",
                instance=scope.get("path"),
                correlation_id=correlation_id,
            ),
            ensure_ascii=False,
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

"""Cabeçalhos de segurança e limite de tamanho do corpo na API (spec 011, FR-171 e FR-174)."""

from __future__ import annotations

import json

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.correlation import correlation_id_var
from app.core.problem import PROBLEM_MEDIA_TYPE, build_problem

MAX_BODY_BYTES = 64 * 1024
DOCS_PATHS = frozenset({"/api/docs", "/api/docs/oauth2-redirect"})

API_HEADERS: tuple[tuple[str, str], ...] = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
)
API_CSP = "default-src 'none'; frame-ancestors 'none'"
# A documentação interativa (Swagger UI) carrega script e estilo de um CDN.
DOCS_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: "
    "https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, max_body: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_body = max_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        csp = DOCS_CSP if scope["path"] in DOCS_PATHS else API_CSP

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in API_HEADERS:
                    headers.setdefault(name, value)
                headers.setdefault("Content-Security-Policy", csp)
            await send(message)

        length = Headers(scope=scope).get("content-length")
        if length is not None and length.isdigit() and int(length) > self.max_body:
            await self._too_large(send_with_headers, scope)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body:
                    raise BodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send_with_headers)
        except BodyTooLargeError:
            await self._too_large(send_with_headers, scope)

    async def _too_large(self, send: Send, scope: Scope) -> None:
        body = json.dumps(
            build_problem(
                status=413,
                detail=f"Corpo da requisição acima de {self.max_body // 1024} KB.",
                instance=scope.get("path"),
                correlation_id=correlation_id_var.get(),
            ),
            ensure_ascii=False,
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class BodyTooLargeError(Exception):
    """Corpo sem Content-Length (chunked) que passou do limite durante a leitura."""

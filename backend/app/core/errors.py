"""Handlers de exceção que respondem no formato Problem Details da RFC 9457 (FR-005)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.correlation import current_correlation_id
from app.core.problem import PROBLEM_MEDIA_TYPE, build_problem

# Mensagens padrão do Starlette (em inglês) que não devem chegar ao usuário.
_STARLETTE_DEFAULT_DETAILS = {"Not Found", "Method Not Allowed"}


def problem_response(
    request: Request,
    status: int,
    *,
    detail: str | None = None,
    extensions: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=build_problem(
            status=status,
            detail=detail,
            instance=request.url.path,
            correlation_id=current_correlation_id(),
            extensions=extensions,
        ),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=dict(headers) if headers else None,
    )


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    detail: str | None = exc.detail if isinstance(exc.detail, str) else None
    if detail in _STARLETTE_DEFAULT_DETAILS:
        detail = None
    return problem_response(request, exc.status_code, detail=detail, headers=exc.headers)


async def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]
    return problem_response(
        request,
        422,
        detail="A requisição contém parâmetros inválidos.",
        extensions={"errors": jsonable_encoder(errors)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    # Exceções não tratadas viram 500 Problem Details no CorrelationIdMiddleware,
    # para que a resposta continue levando o cabeçalho de correlation ID.

"""Fábrica da aplicação FastAPI. Execução: uvicorn app.main:create_app --factory"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.correlation import HEADER_NAME
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware
from app.core.resources import Resources


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, service="api")
    logger = structlog.get_logger("app.lifecycle")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.resources = Resources.create(settings)
        logger.info("api_started", env=settings.app_env, version=settings.app_version)
        try:
            yield
        finally:
            await app.state.resources.close()
            logger.info("api_stopped")

    app = FastAPI(
        title="API da Climate Intelligence Platform",
        description=(
            "Monitoramento meteorológico, análise geoespacial e estimativa de condições "
            "favoráveis a alagamentos. Erros seguem a RFC 9457 (Problem Details)."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET"],
        allow_headers=[HEADER_NAME],
        expose_headers=[HEADER_NAME],
    )
    # Adicionado por último = mais externo: envolve CORS e rotas, então toda resposta leva o id.
    app.add_middleware(CorrelationIdMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)
    return app

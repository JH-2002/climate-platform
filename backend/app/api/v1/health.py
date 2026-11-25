"""Endpoints de vida (liveness) e prontidão (readiness) — FR-002, FR-003."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings, get_settings
from app.core.health import LivenessReport, ReadinessReport, run_readiness
from app.core.resources import Resources, build_readiness_checks
from app.workers.control import make_worker_ping

router = APIRouter(tags=["saúde do sistema"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health", response_model=LivenessReport, summary="Processo ativo (liveness)")
async def liveness(settings: SettingsDep) -> LivenessReport:
    """O processo da API está no ar. Não consulta dependências."""
    return LivenessReport(version=settings.app_version)


@router.get(
    "/health/ready",
    response_model=ReadinessReport,
    summary="Prontidão (readiness)",
    responses={503: {"model": ReadinessReport, "description": "Algum componente indisponível"}},
)
async def readiness(request: Request, response: Response, settings: SettingsDep) -> ReadinessReport:
    """Verifica banco, PostGIS, Redis e workers Celery a cada chamada (sem cache)."""
    resources: Resources = request.app.state.resources
    timeout = settings.readiness_timeout_s
    # O ping do worker usa parte do orçamento; o restante cobre a conexão com o broker.
    checks = build_readiness_checks(resources, make_worker_ping(timeout * 0.6))
    report = await run_readiness(checks, timeout_s=timeout)
    if report.status != "ok":
        response.status_code = 503
    return report

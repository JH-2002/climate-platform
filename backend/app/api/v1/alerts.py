"""Alertas (spec 009): oficiais (Defesa Civil, INMET) e do sistema, sempre separados (BR-140)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.deps import ClockDep, SessionDep, SettingsDep
from app.core.geo import is_valid_coordinate
from app.services.alerts import (
    ActiveAlerts,
    AlertHistory,
    AnyCategory,
    OfficialAlert,
    OfficialAlertDetail,
    RulesInfo,
    active_alerts,
    alert_history,
    alerts_at,
    official_alert_detail,
    rules_info,
    thresholds_from,
)

router = APIRouter(prefix="/alerts", tags=["alertas"])


@router.get(
    "/active",
    response_model=ActiveAlerts,
    summary="Alertas oficiais vigentes e próximos, e alertas do sistema abertos",
)
async def read_active(session: SessionDep, clock: ClockDep) -> ActiveAlerts:
    return await active_alerts(session, clock())


@router.get("", response_model=AlertHistory, summary="Histórico de alertas (até 90 dias)")
async def read_history(
    session: SessionDep,
    clock: ClockDep,
    categoria: AnyCategory | None = None,
    desde: datetime | None = None,
    ate: datetime | None = None,
    pagina: Annotated[int, Query(ge=1, le=1000)] = 1,
) -> AlertHistory:
    try:
        return await alert_history(
            session, clock(), category=categoria, since=desde, until=ate, page=pagina
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get(
    "/official/{alert_id}",
    response_model=OfficialAlertDetail,
    summary="Detalhe de um alerta oficial, com o texto da fonte e a área",
)
async def read_official(alert_id: int, session: SessionDep, clock: ClockDep) -> OfficialAlertDetail:
    detail = await official_alert_detail(session, alert_id, clock())
    if detail is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")
    return detail


@router.get(
    "/at",
    response_model=list[OfficialAlert],
    summary="Alertas oficiais vigentes ou próximos que cobrem um ponto",
)
async def read_at(
    session: SessionDep,
    clock: ClockDep,
    lat: Annotated[float, Query(description="Latitude (WGS84)")],
    lon: Annotated[float, Query(description="Longitude (WGS84)")],
) -> list[OfficialAlert]:
    if not is_valid_coordinate(lat, lon):
        raise HTTPException(status_code=422, detail="Coordenada fora dos limites.")
    return await alerts_at(session, lat, lon, clock())


@router.get("/rules", response_model=RulesInfo, summary="Regras dos alertas do sistema")
async def read_rules(session: SessionDep, settings: SettingsDep) -> RulesInfo:
    return await rules_info(session, thresholds_from(settings))

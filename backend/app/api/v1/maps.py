"""Camadas GeoJSON para o mapa 2D/3D (spec 004)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.deps import ClockDep, SessionDep, SettingsDep
from app.core.geo import BoundingBox
from app.services.alerts import ALERT_ATTRIBUTION, official_alert_features
from app.services.geo import (
    HYDRO_ATTRIBUTION,
    basin_features,
    drainage_features,
    reservoir_features,
)
from app.services.geojson import bbox_polygon, feature_collection, polygon_feature
from app.services.map_layers import forecast_point_features, station_features
from app.services.risk import ATTRIBUTION, DISCLAIMER, occurrence_features, risk_area_features
from app.services.simulation import BANNER, simulation_features
from app.services.simulation import DISCLAIMER as SIMULATION_DISCLAIMER

router = APIRouter(prefix="/map", tags=["mapa"])

GEOJSON = "application/geo+json"
BBOX_HELP = "lon_min,lat_min,lon_max,lat_max (WGS84)"


@router.get("/region", summary="Região de interesse (polígono)")
async def region(settings: SettingsDep) -> dict[str, Any]:
    return polygon_feature(
        bbox_polygon(settings.region), {"name": settings.region_name, "kind": "REGION"}
    )


@router.get("/layers/stations", summary="Estações (FeatureCollection)")
async def stations_layer(
    session: SessionDep,
    bbox: Annotated[str | None, Query(description=BBOX_HELP)] = None,
) -> dict[str, Any]:
    box = None
    if bbox is not None:
        try:
            box = BoundingBox.parse(bbox)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"bbox inválido: {exc}") from None
    features = await station_features(session, box)
    return feature_collection(features, attribution="Fonte: INMET")


@router.get("/layers/forecast-points", summary="Pontos de previsão com chuva prevista em 24 h")
async def forecast_points_layer(session: SessionDep, clock: ClockDep) -> dict[str, Any]:
    """Valores de modelo (`kind = FORECAST`), nunca medições."""
    features = await forecast_point_features(session, clock())
    return feature_collection(features, attribution="Dados de previsão: Open-Meteo.com (CC BY 4.0)")


@router.get("/layers/risk", summary="Setores com risco estimado (polígonos)")
async def risk_layer(session: SessionDep) -> dict[str, Any]:
    """Estimativa experimental do sistema (`kind = DERIVED`), não alerta oficial."""
    features = await risk_area_features(session)
    return feature_collection(features, attribution=ATTRIBUTION, disclaimer=DISCLAIMER)


@router.get("/layers/flood-occurrences", summary="Ocorrências registradas nos últimos 12 meses")
async def flood_occurrences_layer(session: SessionDep, clock: ClockDep) -> dict[str, Any]:
    features = await occurrence_features(session, clock())
    return feature_collection(
        features, attribution="Ocorrências: GeoSampa — Prefeitura de São Paulo (Defesa Civil)"
    )


@router.get("/layers/simulation/{run_id}", summary="Setores de uma simulação (polígonos)")
async def simulation_layer(run_id: uuid.UUID, session: SessionDep) -> dict[str, Any]:
    """Cenário hipotético (`kind = SIMULATED`): não é previsão nem alerta (BR-100)."""
    features = await simulation_features(session, run_id)
    if not features:
        raise HTTPException(status_code=404, detail="Simulação não encontrada.")
    return feature_collection(
        features,
        attribution=f"{BANNER}. Setores: GeoSampa — Prefeitura de São Paulo",
        disclaimer=SIMULATION_DISCLAIMER,
    )


@router.get("/layers/basins", summary="Bacias hidrográficas com setores e risco atual")
async def basins_layer(session: SessionDep, clock: ClockDep) -> dict[str, Any]:
    return feature_collection(await basin_features(session, clock()), attribution=HYDRO_ATTRIBUTION)


@router.get("/layers/drainage", summary="Rios e córregos na área visível")
async def drainage_layer(
    session: SessionDep,
    bbox: Annotated[str, Query(description="lon_min,lat_min,lon_max,lat_max")],
    zoom: Annotated[float, Query(ge=0, le=22)] = 12,
) -> dict[str, Any]:
    try:
        west, south, east, north = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(
            status_code=422, detail="bbox: use lon_min,lat_min,lon_max,lat_max"
        ) from None
    if not (west < east and south < north) or (east - west) * (north - south) > 1.0:
        raise HTTPException(
            status_code=422, detail="bbox inválida ou grande demais (máx. 1 grau²)."
        )
    features, truncated = await drainage_features(session, (west, south, east, north), zoom)
    return feature_collection(
        features,
        attribution=HYDRO_ATTRIBUTION,
        truncated=truncated,
        note=(
            "Abaixo do zoom 12, só os trechos a céu aberto. Aproxime para ver os canalizados "
            "subterrâneos."
        ),
    )


@router.get("/layers/reservoirs", summary="Piscinões (reservatórios de amortecimento)")
async def reservoirs_layer(session: SessionDep) -> dict[str, Any]:
    return feature_collection(await reservoir_features(session), attribution=HYDRO_ATTRIBUTION)


@router.get("/layers/alerts", summary="Alertas oficiais vigentes e próximos (polígonos)")
async def alerts_layer(session: SessionDep, clock: ClockDep) -> dict[str, Any]:
    return feature_collection(
        await official_alert_features(session, clock()), attribution=ALERT_ATTRIBUTION
    )

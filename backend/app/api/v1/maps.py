"""Camadas GeoJSON para o mapa 2D/3D (spec 004)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.deps import ClockDep, SessionDep, SettingsDep
from app.core.geo import BoundingBox
from app.services.geojson import bbox_polygon, feature_collection, polygon_feature
from app.services.map_layers import forecast_point_features, station_features
from app.services.risk import ATTRIBUTION, DISCLAIMER, occurrence_features, risk_area_features

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

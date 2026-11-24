from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    geo,
    health,
    maps,
    risk,
    simulation,
    sources,
    stations,
    weather,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(stations.router)
api_router.include_router(weather.router)
api_router.include_router(maps.router)
api_router.include_router(risk.router)
api_router.include_router(analytics.router)
api_router.include_router(simulation.router)
api_router.include_router(geo.router)

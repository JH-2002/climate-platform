from fastapi import APIRouter

from app.api.v1 import health, maps, sources, stations, weather

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(sources.router)
api_router.include_router(stations.router)
api_router.include_router(weather.router)
api_router.include_router(maps.router)

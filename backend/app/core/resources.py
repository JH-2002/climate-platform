"""Clientes do processo (banco, Redis) e as verificações de prontidão baseadas neles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.health import CheckFn


class PostgisMissingError(RuntimeError):
    pass


@dataclass
class Resources:
    engine: AsyncEngine
    session_factory: async_sessionmaker
    redis: Redis

    @classmethod
    def create(cls, settings: Settings) -> Resources:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=5)
        return cls(
            engine=engine,
            session_factory=async_sessionmaker(engine, expire_on_commit=False),
            redis=Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1),
        )

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def build_readiness_checks(resources: Resources, ping_workers: CheckFn) -> Mapping[str, CheckFn]:
    async def check_db() -> None:
        async with resources.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def check_postgis() -> dict[str, str]:
        async with resources.engine.connect() as conn:
            result = await conn.execute(text("SELECT postgis_lib_version()"))
            version = result.scalar_one_or_none()
        if not version:
            raise PostgisMissingError
        return {"versão": str(version)}

    async def check_redis() -> None:
        await resources.redis.ping()

    return {
        "db": check_db,
        "postgis": check_postgis,
        "redis": check_redis,
        "worker": ping_workers,
    }

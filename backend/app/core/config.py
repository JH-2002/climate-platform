"""Configurações da aplicação, validadas na inicialização (FR-012)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.geo import BoundingBox, parse_points


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: str = Field(min_length=1)
    redis_url: str = Field(min_length=1)

    frontend_origin: str = "http://localhost:3000"
    # O ping do Celery abre conexão com o broker a cada chamada; 5 s evita falsos negativos.
    readiness_timeout_s: float = Field(default=5.0, gt=0, le=10)

    inmet_token: SecretStr | None = None

    # Região de interesse: "lon_min,lat_min,lon_max,lat_max" (WGS84). Padrão: município de SP.
    region_name: str = "Município de São Paulo"
    region_bbox: str = "-46.83,-24.01,-46.36,-23.35"
    # Pontos de previsão: "lat,lon;lat,lon". Padrão: centro de São Paulo.
    forecast_points: str = "-23.55,-46.63"
    http_timeout_s: float = Field(default=15.0, gt=0, le=60)

    @property
    def inmet_token_value(self) -> str | None:
        if self.inmet_token is None:
            return None
        return self.inmet_token.get_secret_value() or None

    @property
    def region(self) -> BoundingBox:
        return BoundingBox.parse(self.region_bbox)

    @property
    def forecast_point_list(self) -> list[tuple[float, float]]:
        return parse_points(self.forecast_points)

    @field_validator("region_bbox")
    @classmethod
    def _validate_bbox(cls, value: str) -> str:
        BoundingBox.parse(value)
        return value

    @field_validator("forecast_points")
    @classmethod
    def _validate_points(cls, value: str) -> str:
        parse_points(value)
        return value

    @field_validator("database_url")
    @classmethod
    def _require_async_postgres(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL deve usar o esquema postgresql+asyncpg://")
        return value

    @field_validator("redis_url")
    @classmethod
    def _require_redis(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL deve usar o esquema redis:// ou rediss://")
        return value


def _emit_startup_error(event: str, **fields: object) -> None:
    """Registra o erro antes de o structlog estar configurado, mantendo o formato JSON."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "error",
        "event": event,
        **fields,
    }
    print(json.dumps(record, ensure_ascii=False), file=sys.stderr)


def load_settings() -> Settings:
    """Carrega as configurações ou encerra o processo com mensagem clara (AC-007)."""
    try:
        return Settings()  # valores vêm das variáveis de ambiente
    except ValidationError as exc:
        missing = [str(err["loc"][0]).upper() for err in exc.errors() if err["type"] == "missing"]
        invalid = [
            {"setting": str(err["loc"][0]).upper(), "reason": err["msg"]}
            for err in exc.errors()
            if err["type"] != "missing"
        ]
        if missing:
            _emit_startup_error("missing_required_setting", settings=missing)
        if invalid:
            _emit_startup_error("invalid_setting", settings=invalid)
        raise SystemExit(1) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()

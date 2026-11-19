"""Configuração compartilhada dos testes. Valores só para APP_ENV=test (BR-002)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

_TEST_ENV = {
    "LOG_LEVEL": "INFO",
    # Na integração estes valores vêm dos serviços reais (README › Testes).
    "DATABASE_URL": "postgresql+asyncpg://climate:test@localhost:5433/climate",
    "REDIS_URL": "redis://localhost:6379/15",
}
os.environ["APP_ENV"] = "test"  # sempre: mantém dados de teste fora dos outros ambientes
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)


@pytest.fixture(autouse=True)
def _fresh_settings_cache() -> Iterator[None]:
    try:
        from app.core.config import get_settings
    except ImportError:  # sem pydantic-settings instalado: os testes puros continuam rodando
        yield
        return
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

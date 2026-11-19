"""Utilitários de correlation ID (FR-004). Puros, independentes de framework."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

HEADER_NAME = "X-Correlation-ID"
_VALID = re.compile(r"^[A-Za-z0-9._\-]{1,128}$")

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def resolve_correlation_id(incoming: str | None) -> str:
    """Aceita o id enviado pelo cliente só se for seguro para log; senão, gera um novo."""
    if incoming and _VALID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def current_correlation_id() -> str | None:
    return correlation_id_var.get()

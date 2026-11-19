"""Remoção de valores sensíveis dos eventos de log (Constituição §5)."""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(r"(token|secret|password|passwd|authorization|api_key|cookie)", re.I)
_URL_CREDENTIALS = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^:/@\s]+):[^@/\s]+@", re.IGNORECASE
)


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY.search(key))


def redact_text(value: str) -> str:
    """Oculta senhas embutidas em URLs de conexão."""
    return _URL_CREDENTIALS.sub(rf"\g<scheme>\g<user>:{REDACTED}@", value)


def redact_value(key: str, value: Any) -> Any:
    if is_sensitive_key(key):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(k): redact_value(str(k), v) for k, v in value.items()}
    return value


def redact_event(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Processador do structlog."""
    for key in list(event_dict.keys()):
        event_dict[key] = redact_value(key, event_dict[key])
    return event_dict

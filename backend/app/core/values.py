"""Conversão de valores vindos do banco.

O SQLAlchemy 2.1 tipa as colunas de agregados (count, sum, extract) como ``object``; estas
funções deixam a conversão explícita e funcionam igual no 2.0.
"""

from __future__ import annotations

from typing import Any


def to_int(value: Any) -> int:
    return int(value)


def to_float(value: Any) -> float:
    return float(value)

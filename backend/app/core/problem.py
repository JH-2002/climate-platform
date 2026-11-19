"""Payloads Problem Details da RFC 9457 (FR-005). Funções puras, sem dependência de framework."""

from __future__ import annotations

from typing import Any

PROBLEM_MEDIA_TYPE = "application/problem+json"

_TITLES: dict[int, str] = {
    400: "Requisição inválida",
    401: "Não autenticado",
    403: "Acesso negado",
    404: "Recurso não encontrado",
    405: "Método não permitido",
    409: "Conflito",
    422: "Parâmetros inválidos",
    429: "Muitas requisições",
    500: "Erro interno",
    502: "Falha em serviço externo",
    503: "Serviço indisponível",
    504: "Tempo de resposta esgotado",
}


def default_title(status: int) -> str:
    return _TITLES.get(status, "Erro")


def build_problem(
    *,
    status: int,
    title: str | None = None,
    detail: str | None = None,
    instance: str | None = None,
    correlation_id: str | None = None,
    type_: str = "about:blank",
    extensions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reserved = {"type", "title", "status", "detail", "instance", "correlation_id"}
    if extensions and reserved & extensions.keys():
        clash = sorted(reserved & extensions.keys())
        raise ValueError(f"extensões não podem sobrescrever membros reservados: {clash}")

    problem: dict[str, Any] = {
        "type": type_,
        "title": title or default_title(status),
        "status": status,
    }
    if detail is not None:
        problem["detail"] = detail
    if instance is not None:
        problem["instance"] = instance
    problem["correlation_id"] = correlation_id
    if extensions:
        problem.update(extensions)
    return problem

"""Central de relatórios (spec 010): pedidos, andamento e download."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.api.v1.deps import ClockDep, SessionDep
from app.services.reports import (
    REPORT_TYPES,
    ReportFormat,
    ReportLimitError,
    ReportParamsError,
    ReportRequest,
    ReportType,
    ReportTypeInfo,
    create_request,
    get_file,
    get_request,
    list_requests,
)

router = APIRouter(prefix="/reports", tags=["relatórios"])

GENERATE_TASK = "reports.generate"
Enqueue = Callable[[str], Awaitable[None]]


def get_enqueuer() -> Enqueue:
    """Envia a geração ao worker. Os testes trocam por uma geração direta."""

    async def enqueue(request_id: str) -> None:
        from app.workers.dispatch import send_task

        await send_task(GENERATE_TASK, request_id)

    return enqueue


EnqueueDep = Annotated[Enqueue, Depends(get_enqueuer)]


class ReportCreate(BaseModel):
    type: ReportType
    format: ReportFormat
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/types", response_model=list[ReportTypeInfo], summary="Tipos de relatório")
async def read_types() -> list[ReportTypeInfo]:
    return list(REPORT_TYPES.values())


@router.post("", response_model=ReportRequest, status_code=202, summary="Pede um relatório")
async def create(
    body: ReportCreate, session: SessionDep, clock: ClockDep, enqueue: EnqueueDep
) -> ReportRequest:
    try:
        request = await create_request(session, body.type, body.format, body.params, clock())
    except ReportParamsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except ReportLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from None
    await enqueue(str(request.id))
    return request


@router.get("", response_model=list[ReportRequest], summary="Pedidos deste navegador")
async def read_list(
    session: SessionDep,
    clock: ClockDep,
    ids: Annotated[str, Query(description="Ids separados por vírgula (até 50)")] = "",
) -> list[ReportRequest]:
    parsed: list[uuid.UUID] = []
    for raw in [part.strip() for part in ids.split(",") if part.strip()][:50]:
        try:
            parsed.append(uuid.UUID(raw))
        except ValueError:
            continue
    return await list_requests(session, parsed, clock())


@router.get("/{request_id}", response_model=ReportRequest, summary="Andamento de um pedido")
async def read_one(request_id: uuid.UUID, session: SessionDep, clock: ClockDep) -> ReportRequest:
    request = await get_request(session, request_id, clock())
    if request is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    return request


@router.get("/{request_id}/download", summary="Baixa o arquivo do relatório")
async def download(request_id: uuid.UUID, session: SessionDep, clock: ClockDep) -> Response:
    request = await get_request(session, request_id, clock())
    if request is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    if request.status == "EXPIRED":
        raise HTTPException(status_code=410, detail="O relatório passou dos 7 dias e foi apagado.")
    if request.status != "DONE":
        raise HTTPException(status_code=409, detail="O relatório ainda não está pronto.")
    file = await get_file(session, request_id)
    if file is None:
        raise HTTPException(status_code=410, detail="O arquivo do relatório não existe mais.")
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file.filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )

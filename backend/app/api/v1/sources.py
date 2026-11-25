"""Estado das fontes de dados (FR-030)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.deps import SessionDep, SettingsDep
from app.services.sources import SourceStatus, list_source_status

router = APIRouter(prefix="/sources", tags=["fontes de dados"])


class SourceStatusList(BaseModel):
    checked_at: datetime
    items: list[SourceStatus]


@router.get("/status", response_model=SourceStatusList, summary="Frescor de cada fonte")
async def sources_status(session: SessionDep, settings: SettingsDep) -> SourceStatusList:
    """Frescor calculado na leitura (BR-020): um dado antigo nunca aparece como atual."""
    now = datetime.now(UTC)
    credentials = {"inmet-observations": settings.inmet_token_value is not None}
    items = await list_source_status(session, now=now, credentials=credentials)
    return SourceStatusList(checked_at=now, items=items)

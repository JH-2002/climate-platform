"""Estado das fontes de dados (FR-030)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import data_sources
from app.services.freshness import Freshness, Reason, classify_freshness


class SourceStatus(BaseModel):
    code: str
    name: str
    owner: str
    url: str
    license: str
    attribution: str
    access_method: str
    expected_interval_s: int
    freshness: Freshness
    reason: Reason
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_run_status: str | None
    last_error: str | None


async def list_source_status(
    session: AsyncSession, *, now: datetime, credentials: dict[str, bool]
) -> list[SourceStatus]:
    """`credentials`: código da fonte -> se a credencial exigida está configurada."""
    rows = (await session.execute(select(data_sources).order_by(data_sources.c.code))).all()
    items: list[SourceStatus] = []
    for row in rows:
        missing = bool(row.requires_credentials) and not credentials.get(row.code, False)
        result = classify_freshness(
            now=now,
            last_success_at=row.last_success_at,
            expected_interval_s=row.expected_interval_s,
            last_run_status=row.last_status,
            credentials_missing=missing,
            enabled=row.enabled,
        )
        items.append(
            SourceStatus(
                code=row.code,
                name=row.name,
                owner=row.owner,
                url=row.url,
                license=row.license,
                attribution=row.attribution,
                access_method=row.access_method,
                expected_interval_s=row.expected_interval_s,
                freshness=result.freshness,
                reason=result.reason,
                last_success_at=row.last_success_at,
                last_attempt_at=row.last_attempt_at,
                last_run_status=row.last_status,
                last_error=row.last_error,
            )
        )
    return items

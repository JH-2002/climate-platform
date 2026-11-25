"""Execução de uma ingestão com registro em `ingestion_runs` (FR-023), payload bruto
deduplicado (FR-024) e circuit breaker por fonte (NFR-020, AC-023).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.redaction import redact_text
from app.models.tables import data_sources, ingestion_runs, raw_payloads

logger = structlog.get_logger(__name__)

CIRCUIT_THRESHOLD = 5
CIRCUIT_COOLDOWN = timedelta(minutes=10)
ERROR_SUMMARY_MAX = 500


class SourceNotFoundError(LookupError):
    pass


@dataclass
class JobResult:
    received: int = 0
    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RunOutcome:
    run_id: int | None
    status: str
    result: JobResult
    error: str | None = None


def circuit_is_open(
    recent: Sequence[tuple[str, datetime]],
    now: datetime,
    threshold: int = CIRCUIT_THRESHOLD,
    cooldown: timedelta = CIRCUIT_COOLDOWN,
) -> bool:
    """`recent`: (status, started_at) das execuções, da mais recente para a mais antiga.

    Abre quando as `threshold` últimas falharam e a mais recente foi há menos de `cooldown`.
    """
    if len(recent) < threshold:
        return False
    window = recent[:threshold]
    if any(status != "FAILED" for status, _ in window):
        return False
    return now - window[0][1] < cooldown


def final_status(result: JobResult) -> str:
    if result.rejected and (result.inserted or result.updated):
        return "PARTIAL"
    if result.rejected and result.received and not (result.inserted or result.updated):
        return "FAILED"
    return "SUCCESS"


def summarize_error(exc: BaseException) -> str:
    message = redact_text(f"{type(exc).__name__}: {exc}")
    return message[:ERROR_SUMMARY_MAX]


@dataclass
class IngestionContext:
    session: AsyncSession
    source_id: int
    run_id: int
    now: datetime

    async def store_raw(self, payload: Any, request_url: str) -> int:
        """Guarda o payload bruto (antes de normalizar). Payload idêntico não é duplicado."""
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        stmt = (
            insert(raw_payloads)
            .values(
                source_id=self.source_id,
                run_id=self.run_id,
                content_hash=content_hash,
                request_url=redact_text(request_url),
                payload=payload,
                fetched_at=self.now,
            )
            .on_conflict_do_nothing(index_elements=["source_id", "content_hash"])
            .returning(raw_payloads.c.id)
        )
        new_id = (await self.session.execute(stmt)).scalar_one_or_none()
        if new_id is not None:
            return int(new_id)
        existing = await self.session.execute(
            select(raw_payloads.c.id).where(
                raw_payloads.c.source_id == self.source_id,
                raw_payloads.c.content_hash == content_hash,
            )
        )
        return int(existing.scalar_one())


Job = Callable[[IngestionContext], Awaitable[JobResult]]


async def run_ingestion(
    session_factory: async_sessionmaker[AsyncSession],
    source_code: str,
    job: Job,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RunOutcome:
    started = now()
    async with session_factory() as session:
        source = (
            await session.execute(
                select(data_sources.c.id, data_sources.c.enabled).where(
                    data_sources.c.code == source_code
                )
            )
        ).one_or_none()
        if source is None:
            raise SourceNotFoundError(source_code)
        source_id = int(source.id)

        recent = (
            await session.execute(
                select(ingestion_runs.c.status, ingestion_runs.c.started_at)
                .where(ingestion_runs.c.source_id == source_id)
                .order_by(ingestion_runs.c.started_at.desc())
                .limit(CIRCUIT_THRESHOLD)
            )
        ).all()
        circuit_open = circuit_is_open([(r.status, r.started_at) for r in recent], started)

        run_id = int(
            (
                await session.execute(
                    insert(ingestion_runs)
                    .values(source_id=source_id, started_at=started, status="RUNNING")
                    .returning(ingestion_runs.c.id)
                )
            ).scalar_one()
        )
        await session.commit()

        if circuit_open:
            error = "circuit_open: 5 falhas seguidas; nova tentativa após 10 min"
            await _finish(session, source_id, run_id, "FAILED", JobResult(), error, now())
            logger.warning("ingestion_skipped_circuit_open", source=source_code, run_id=run_id)
            return RunOutcome(run_id, "FAILED", JobResult(), error)

        context = IngestionContext(session, source_id, run_id, started)
        try:
            result = await job(context)
        except Exception as exc:
            await session.rollback()
            error = summarize_error(exc)
            await _finish(session, source_id, run_id, "FAILED", JobResult(), error, now())
            logger.warning("ingestion_failed", source=source_code, run_id=run_id, error=error)
            return RunOutcome(run_id, "FAILED", JobResult(), error)

        status = final_status(result)
        notes = "; ".join(result.notes)[:ERROR_SUMMARY_MAX] or None
        await _finish(session, source_id, run_id, status, result, notes, now())
        logger.info(
            "ingestion_finished",
            source=source_code,
            run_id=run_id,
            status=status,
            received=result.received,
            inserted=result.inserted,
            updated=result.updated,
            rejected=result.rejected,
        )
        return RunOutcome(run_id, status, result, notes)


async def _finish(
    session: AsyncSession,
    source_id: int,
    run_id: int,
    status: str,
    result: JobResult,
    error: str | None,
    finished_at: datetime,
) -> None:
    await session.execute(
        update(ingestion_runs)
        .where(ingestion_runs.c.id == run_id)
        .values(
            finished_at=finished_at,
            status=status,
            records_received=result.received,
            records_inserted=result.inserted,
            records_updated=result.updated,
            records_rejected=result.rejected,
            error_summary=error,
        )
    )
    values: dict[str, Any] = {
        "last_attempt_at": finished_at,
        "last_status": status,
        "last_error": error if status == "FAILED" else None,
    }
    if status in ("SUCCESS", "PARTIAL"):
        values["last_success_at"] = finished_at
    await session.execute(update(data_sources).where(data_sources.c.id == source_id).values(values))
    await session.commit()

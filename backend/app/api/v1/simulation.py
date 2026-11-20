"""Laboratório de simulação (spec 007). Cenários hipotéticos: não são previsão nem alerta."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.v1.deps import ClockDep, SessionDep
from app.services.risk import list_subprefectures
from app.services.simulation import (
    BANNER,
    DISCLAIMER,
    Center,
    PresetOut,
    SimulatedSector,
    SimulationRun,
    SimulationUnavailableError,
    get_run,
    list_sectors,
    presets,
    run_simulation,
    sector_detail,
    subprefecture_centers,
)
from app.simulation.scenario import (
    PRESETS,
    Cell,
    Hybrid,
    Pattern,
    Scenario,
    ScenarioError,
    Uncertainty,
)

router = APIRouter(prefix="/simulation", tags=["simulação"])

CategoryFilter = Literal["LOW", "MODERATE", "HIGH", "CRITICAL", "UNKNOWN"]


class CellIn(BaseModel):
    latitude: float
    longitude: float
    radius_km: float


class ScenarioIn(BaseModel):
    """Os limites são conferidos pelo motor (BR-104), com mensagem em português."""

    mode: Literal["SIMULATION", "HYBRID"] = "SIMULATION"
    total_mm: float = 0.0
    duration_h: int = 1
    pattern: Pattern = Pattern.CONSTANT
    antecedent_mm: float = 0.0
    cell: CellIn | None = None
    # HYBRID (FR-109): previsão real × multiplicador, com ou sem a chuva do cenário.
    multiplier: float = 1.0
    add_storm: bool = False
    # Variações com seed (FR-108).
    members: int = 1
    intensity_pct: float = 0.0
    shift_km: float = 0.0
    seed: int | None = None
    preset: str | None = Field(default=None, max_length=60)
    repeat_of: uuid.UUID | None = None

    def to_scenario(self) -> Scenario:
        cell = None if self.cell is None else Cell(**self.cell.model_dump())
        return Scenario(
            total_mm=self.total_mm,
            duration_h=self.duration_h,
            pattern=self.pattern,
            antecedent_mm=self.antecedent_mm,
            cell=cell,
        )

    def to_hybrid(self) -> Hybrid | None:
        if self.mode != "HYBRID":
            return None
        return Hybrid(multiplier=self.multiplier, add_storm=self.add_storm)

    def to_uncertainty(self) -> Uncertainty:
        return Uncertainty(
            members=self.members, intensity_pct=self.intensity_pct, shift_km=self.shift_km
        )


class SimulatedSectorPage(BaseModel):
    items: list[SimulatedSector]
    total: int
    limit: int
    offset: int
    subprefectures: list[str]
    banner: str = BANNER
    disclaimer: str = DISCLAIMER


async def _run_or_404(session: SessionDep, run_id: uuid.UUID, clock: ClockDep) -> SimulationRun:
    run = await get_run(session, run_id, now=clock())
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Simulação não encontrada. As simulações ficam guardadas por 30 dias.",
        )
    return run


@router.get("/presets", response_model=list[PresetOut], summary="Cenários prontos")
async def list_presets() -> list[PresetOut]:
    return presets()


@router.get(
    "/centers", response_model=list[Center], summary="Centros das subprefeituras para a célula"
)
async def list_centers(session: SessionDep) -> list[Center]:
    return await subprefecture_centers(session)


@router.post("/runs", response_model=SimulationRun, status_code=201, summary="Executa um cenário")
async def create_run(body: ScenarioIn, session: SessionDep, clock: ClockDep) -> SimulationRun:
    if body.preset is not None and body.preset not in {p.code for p in PRESETS}:
        raise HTTPException(status_code=422, detail=f"Cenário pronto desconhecido: {body.preset}")
    now = clock()
    if body.repeat_of is not None and await get_run(session, body.repeat_of, now=now) is None:
        raise HTTPException(status_code=404, detail="Simulação original não encontrada.")
    try:
        return await run_simulation(
            session,
            body.to_scenario(),
            now=now,
            preset=body.preset,
            hybrid=body.to_hybrid(),
            uncertainty=body.to_uncertainty(),
            seed=body.seed,
            repeat_of=body.repeat_of,
        )
    except ScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except HybridUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except SimulationUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/runs", response_model=list[RunListItem], summary="Simulações recentes")
async def recent_runs(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[RunListItem]:
    return await list_runs(session, limit)


@router.get("/runs/{run_id}", response_model=SimulationRun, summary="Resultado de uma simulação")
async def read_run(run_id: uuid.UUID, session: SessionDep, clock: ClockDep) -> SimulationRun:
    return await _run_or_404(session, run_id, clock)


@router.get(
    "/runs/{run_id}/sectors",
    response_model=SimulatedSectorPage,
    summary="Setores simulados, do maior para o menor risco",
)
async def read_sectors(
    run_id: uuid.UUID,
    session: SessionDep,
    clock: ClockDep,
    category: CategoryFilter | None = None,
    subprefecture: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SimulatedSectorPage:
    await _run_or_404(session, run_id, clock)
    items, total = await list_sectors(
        session,
        run_id,
        category=category,
        subprefecture=subprefecture,
        limit=limit,
        offset=offset,
    )
    return SimulatedSectorPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        subprefectures=await list_subprefectures(session),
    )


@router.get(
    "/runs/{run_id}/sectors/{sector_id}",
    response_model=SimulatedSector,
    summary="Explicação de um setor simulado",
)
async def read_sector(
    run_id: uuid.UUID, sector_id: int, session: SessionDep, clock: ClockDep
) -> SimulatedSector:
    await _run_or_404(session, run_id, clock)
    sector = await sector_detail(session, run_id, sector_id)
    if sector is None:
        raise HTTPException(status_code=404, detail="Setor não encontrado nesta simulação.")
    return sector

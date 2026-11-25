"""Laboratório de simulação (spec 007): execuções e resultados simulados, separados do real.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _run_each(sql: str) -> None:
    """O asyncpg não aceita vários comandos numa execução; envia um por vez."""
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _run_each(
        """
        CREATE TABLE simulation_runs (
            id uuid PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now(),
            kind text NOT NULL DEFAULT 'SIMULATED' CHECK (kind = 'SIMULATED'),
            mode text NOT NULL CHECK (mode IN ('SIMULATION', 'HYBRID')),
            scenario jsonb NOT NULL,
            preset text,
            seed bigint,
            members integer NOT NULL DEFAULT 1 CHECK (members BETWEEN 1 AND 100),
            simulation_engine_version text NOT NULL,
            risk_engine_version text NOT NULL,
            sectors_fingerprint text NOT NULL,
            sector_count integer NOT NULL,
            forecast_issued_at timestamptz,
            counts jsonb NOT NULL,
            comparison jsonb NOT NULL,
            duration_ms integer NOT NULL
        );
        CREATE INDEX ix_simulation_runs_created ON simulation_runs (created_at DESC);

        CREATE TABLE simulation_results (
            run_id uuid NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
            sector_id integer NOT NULL REFERENCES hydro_risk_sectors(id),
            category text NOT NULL,
            p_high double precision,
            p_critical double precision,
            rain_level smallint,
            susceptibility smallint NOT NULL,
            p1h_max_mm double precision,
            p24_mm double precision,
            a72_mm double precision,
            rain_factor double precision NOT NULL,
            distance_km double precision,
            factors jsonb NOT NULL,
            PRIMARY KEY (run_id, sector_id)
        )
        """
    )


def downgrade() -> None:
    _run_each(
        """
        DROP TABLE IF EXISTS simulation_results;
        DROP TABLE IF EXISTS simulation_runs
        """
    )

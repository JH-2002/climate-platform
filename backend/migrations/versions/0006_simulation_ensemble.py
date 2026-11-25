"""Laboratório de simulação, Parte B: resumo das variações e repetição de execuções.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE simulation_runs ADD COLUMN ensemble jsonb")
    op.execute(
        "ALTER TABLE simulation_runs ADD COLUMN repeat_of uuid "
        "REFERENCES simulation_runs(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE simulation_runs DROP COLUMN IF EXISTS repeat_of")
    op.execute("ALTER TABLE simulation_runs DROP COLUMN IF EXISTS ensemble")

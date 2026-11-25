"""Central de relatórios (spec 010): pedidos e arquivos gerados.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
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
        CREATE TABLE report_requests (
            id uuid PRIMARY KEY,
            report_type text NOT NULL
                CHECK (report_type IN ('situacao', 'risco', 'alertas', 'chuva', 'simulacao')),
            format text NOT NULL CHECK (format IN ('pdf', 'csv', 'json')),
            params jsonb NOT NULL DEFAULT '{}',
            title text NOT NULL,
            mode text NOT NULL CHECK (mode IN ('REAL', 'SIMULATION')),
            status text NOT NULL
                CHECK (status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'EXPIRED')),
            error text,
            created_at timestamptz NOT NULL,
            started_at timestamptz,
            finished_at timestamptz,
            expires_at timestamptz,
            bytes integer,
            sha256 text,
            filename text,
            media_type text
        );
        CREATE INDEX ix_report_requests_created ON report_requests (created_at);
        CREATE INDEX ix_report_requests_status ON report_requests (status);

        CREATE TABLE report_files (
            request_id uuid PRIMARY KEY REFERENCES report_requests(id) ON DELETE CASCADE,
            content bytea NOT NULL
        )
        """
    )


def downgrade() -> None:
    _run_each(
        """
        DROP TABLE IF EXISTS report_files;
        DROP TABLE IF EXISTS report_requests
        """
    )

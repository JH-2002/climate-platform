"""Avaliação retrospectiva do motor de risco (spec 015): previsões arquivadas e avaliações.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
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
        CREATE TABLE forecast_archive_hourly (
            source_id integer NOT NULL REFERENCES data_sources(id),
            point_key text NOT NULL,
            valid_at timestamptz NOT NULL,
            precipitation_mm real NOT NULL CHECK (precipitation_mm >= 0),
            ingested_at timestamptz NOT NULL,
            PRIMARY KEY (point_key, valid_at)
        );
        CREATE TABLE risk_evaluations (
            id serial PRIMARY KEY,
            computed_at timestamptz NOT NULL,
            engine_version text NOT NULL,
            period_start date,
            period_end date,
            status text NOT NULL CHECK (status IN ('SUCCESS', 'FAILED')),
            result jsonb,
            error text
        );
        CREATE INDEX ix_risk_evaluations_computed ON risk_evaluations (computed_at DESC)
        """
    )
    _run_each(
        """
        INSERT INTO data_sources (code, name, owner, url, license, attribution, access_method,
                                  expected_interval_s, requires_credentials)
        VALUES
          ('open-meteo-historical-forecast', 'Open-Meteo — previsões arquivadas (chuva horária)',
           'Open-Meteo', 'https://historical-forecast-api.open-meteo.com/v1/forecast',
           'CC BY 4.0', 'Previsão arquivada: Open-Meteo.com (CC BY 4.0)',
           'API REST (JSON), sem token', 86400, false)
        """
    )


def downgrade() -> None:
    _run_each(
        """
        DROP TABLE IF EXISTS risk_evaluations;
        DROP TABLE IF EXISTS forecast_archive_hourly;
        DELETE FROM raw_payloads WHERE source_id IN
            (SELECT id FROM data_sources WHERE code = 'open-meteo-historical-forecast');
        DELETE FROM ingestion_runs WHERE source_id IN
            (SELECT id FROM data_sources WHERE code = 'open-meteo-historical-forecast');
        DELETE FROM data_sources WHERE code = 'open-meteo-historical-forecast'
        """
    )

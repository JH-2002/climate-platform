"""Análises (spec 006): reanálise diária, chuva mensal medida do IAG/USP e carga inicial.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
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
        CREATE TABLE climate_daily (
            id bigserial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            point_key text NOT NULL,
            point geography(Point, 4326) NOT NULL,
            cell_key text NOT NULL,
            day date NOT NULL,
            variable text NOT NULL,
            value double precision NOT NULL,
            unit text NOT NULL,
            kind text NOT NULL DEFAULT 'MODELED' CHECK (kind = 'MODELED'),
            raw_payload_id bigint REFERENCES raw_payloads(id),
            ingested_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source_id, point_key, day, variable)
        );
        CREATE INDEX ix_climate_daily_series ON climate_daily (point_key, variable, day);

        CREATE TABLE rain_monthly_observed (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            station_code text NOT NULL,
            year smallint NOT NULL CHECK (year BETWEEN 1800 AND 2200),
            month smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
            value_mm double precision NOT NULL CHECK (value_mm >= 0),
            kind text NOT NULL DEFAULT 'OBSERVED' CHECK (kind = 'OBSERVED'),
            source_file text NOT NULL,
            file_hash text NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source_id, station_code, year, month)
        );

        CREATE TABLE published_normals (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            station_code text NOT NULL,
            period text NOT NULL,
            month smallint NOT NULL CHECK (month BETWEEN 0 AND 12),
            value_mm double precision NOT NULL,
            UNIQUE (source_id, station_code, period, month)
        );

        CREATE TABLE backfill_progress (
            source_id integer NOT NULL REFERENCES data_sources(id),
            point_key text NOT NULL,
            loaded_until date,
            completed boolean NOT NULL DEFAULT false,
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (source_id, point_key)
        )
        """
    )
    _run_each(
        """
        INSERT INTO data_sources (code, name, owner, url, license, attribution, access_method,
                                  expected_interval_s, requires_credentials)
        VALUES
          ('open-meteo-archive', 'Open-Meteo — reanálise diária (ERA5/ERA5-Land)',
           'Open-Meteo (dados Copernicus/ECMWF)', 'https://archive-api.open-meteo.com/v1/archive',
           'CC BY 4.0 (uso não comercial da API gratuita)',
           'Reanálise: Open-Meteo.com (CC BY 4.0), dados ERA5/ERA5-Land (Copernicus)',
           'API REST (JSON), sem token', 86400, false),
          ('iag-usp-rain-monthly', 'IAG/USP — chuva mensal medida (Água Funda), 1933–2025',
           'IAG/USP; publicação: Prefeitura de São Paulo (SMUL/Geoinfo)',
           'https://prefeitura.sp.gov.br/documents/d/licenciamento/precipitacao_pluviometrica_1933_2025',
           'Dado público municipal (termos não informados)',
           'Chuva medida: IAG/USP — Estação Água Funda; publicação: Prefeitura de São Paulo',
           'PDF anual; CSV de referência no repositório', 34560000, false)
        """
    )


def downgrade() -> None:
    _run_each(
        """
        DROP TABLE IF EXISTS backfill_progress;
        DROP TABLE IF EXISTS published_normals;
        DROP TABLE IF EXISTS rain_monthly_observed;
        DROP TABLE IF EXISTS climate_daily;
        DELETE FROM raw_payloads WHERE source_id IN (
            SELECT id FROM data_sources WHERE code IN ('open-meteo-archive',
            'iag-usp-rain-monthly'));
        DELETE FROM ingestion_runs WHERE source_id IN (
            SELECT id FROM data_sources WHERE code IN ('open-meteo-archive',
            'iag-usp-rain-monthly'));
        DELETE FROM data_sources WHERE code IN ('open-meteo-archive', 'iag-usp-rain-monthly')
        """
    )

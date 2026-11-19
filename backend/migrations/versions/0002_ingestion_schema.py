"""Esquema de ingestão: fontes, estações, execuções, payloads, observações e previsões.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATUSES = "('RUNNING','SUCCESS','PARTIAL','FAILED')"
QUALITY_FLAGS = "('OK','SUSPECT','FAILED','UNCHECKED')"
MODES = "('REAL','SIMULATION','HYBRID')"


def _run_each(sql: str) -> None:
    """O asyncpg não aceita vários comandos numa execução; envia um por vez."""
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _run_each(
        f"""
        CREATE TABLE data_sources (
            id serial PRIMARY KEY,
            code text NOT NULL UNIQUE,
            name text NOT NULL,
            owner text NOT NULL,
            url text NOT NULL,
            license text NOT NULL,
            attribution text NOT NULL,
            access_method text NOT NULL,
            expected_interval_s integer NOT NULL CHECK (expected_interval_s > 0),
            requires_credentials boolean NOT NULL DEFAULT false,
            enabled boolean NOT NULL DEFAULT true,
            last_attempt_at timestamptz,
            last_success_at timestamptz,
            last_status text CHECK (last_status IN {RUN_STATUSES}),
            last_error text,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE weather_stations (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            external_code text NOT NULL,
            name text NOT NULL,
            state text,
            location geography(Point, 4326) NOT NULL,
            altitude_m double precision,
            status text NOT NULL
                CHECK (status IN ('OPERATIONAL','FAULT','INACTIVE','UNKNOWN')),
            source_status text,
            started_at timestamptz,
            ended_at timestamptz,
            first_seen_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL,
            UNIQUE (source_id, external_code)
        );
        CREATE INDEX ix_weather_stations_location ON weather_stations USING gist (location);

        CREATE TABLE ingestion_runs (
            id bigserial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            status text NOT NULL CHECK (status IN {RUN_STATUSES}),
            records_received integer NOT NULL DEFAULT 0,
            records_inserted integer NOT NULL DEFAULT 0,
            records_updated integer NOT NULL DEFAULT 0,
            records_rejected integer NOT NULL DEFAULT 0,
            error_summary text
        );
        CREATE INDEX ix_ingestion_runs_source_started
            ON ingestion_runs (source_id, started_at DESC);

        CREATE TABLE raw_payloads (
            id bigserial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            run_id bigint NOT NULL REFERENCES ingestion_runs(id),
            content_hash text NOT NULL,
            request_url text NOT NULL,
            payload jsonb NOT NULL,
            fetched_at timestamptz NOT NULL,
            UNIQUE (source_id, content_hash)
        );

        CREATE TABLE weather_observations (
            id bigserial PRIMARY KEY,
            station_id integer NOT NULL REFERENCES weather_stations(id),
            source_id integer NOT NULL REFERENCES data_sources(id),
            observed_at timestamptz NOT NULL,
            variable text NOT NULL,
            value double precision,
            unit text NOT NULL,
            kind text NOT NULL DEFAULT 'OBSERVED' CHECK (kind = 'OBSERVED'),
            mode text NOT NULL DEFAULT 'REAL' CHECK (mode IN {MODES}),
            quality_flag text NOT NULL DEFAULT 'UNCHECKED' CHECK (quality_flag IN {QUALITY_FLAGS}),
            quality_reason text,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            ingested_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (station_id, variable, observed_at)
        );
        CREATE INDEX ix_weather_observations_observed_at ON weather_observations (observed_at);

        CREATE TABLE weather_forecasts (
            id bigserial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            point geography(Point, 4326) NOT NULL,
            point_key text NOT NULL,
            resolution text NOT NULL CHECK (resolution IN ('hourly','daily')),
            valid_at timestamptz NOT NULL,
            variable text NOT NULL,
            value double precision NOT NULL,
            unit text NOT NULL,
            issued_at timestamptz NOT NULL,
            kind text NOT NULL DEFAULT 'FORECAST' CHECK (kind = 'FORECAST'),
            mode text NOT NULL DEFAULT 'REAL' CHECK (mode IN {MODES}),
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, point_key, resolution, variable, valid_at)
        );
        CREATE INDEX ix_weather_forecasts_point ON weather_forecasts USING gist (point);
        CREATE INDEX ix_weather_forecasts_valid_at ON weather_forecasts (valid_at);
        """
    )
    _run_each(
        """
        INSERT INTO data_sources (code, name, owner, url, license, attribution, access_method,
                                  expected_interval_s, requires_credentials)
        VALUES
          ('inmet-stations', 'INMET — estações automáticas (cadastro)',
           'Instituto Nacional de Meteorologia', 'https://apitempo.inmet.gov.br/estacoes/T',
           'Dados públicos federais', 'Fonte: INMET', 'API REST (JSON), sem token', 86400, false),
          ('inmet-observations', 'INMET — observações horárias',
           'Instituto Nacional de Meteorologia', 'https://apitempo.inmet.gov.br',
           'Dados públicos federais', 'Fonte: INMET', 'API REST (JSON), com token', 3600, true),
          ('open-meteo-forecast', 'Open-Meteo — previsão do tempo',
           'Open-Meteo', 'https://api.open-meteo.com/v1/forecast',
           'CC BY 4.0 (uso não comercial da API gratuita)',
           'Dados de previsão: Open-Meteo.com (CC BY 4.0)', 'API REST (JSON), sem token',
           3600, false);
        """
    )


def downgrade() -> None:
    _run_each(
        """
        DROP TABLE IF EXISTS weather_forecasts;
        DROP TABLE IF EXISTS weather_observations;
        DROP TABLE IF EXISTS raw_payloads;
        DROP TABLE IF EXISTS ingestion_runs;
        DROP TABLE IF EXISTS weather_stations;
        DROP TABLE IF EXISTS data_sources;
        """
    )

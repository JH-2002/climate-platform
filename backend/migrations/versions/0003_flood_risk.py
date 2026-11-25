"""Risco de alagamento v0 (spec 005): camadas do GeoSampa e execuções do motor.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = "('LOW','MODERATE','HIGH','CRITICAL','UNKNOWN')"


def _run_each(sql: str) -> None:
    """O asyncpg não aceita vários comandos numa execução; envia um por vez."""
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _run_each(
        f"""
        CREATE TABLE hydro_risk_sectors (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            source_code text NOT NULL,
            area_code text,
            area_name text,
            grade smallint NOT NULL CHECK (grade BETWEEN 1 AND 4),
            processes text[] NOT NULL DEFAULT '{{}}',
            households integer CHECK (households >= 0),
            subprefecture text,
            basin text,
            inspected_on date,
            geom geometry(MultiPolygon, 4326) NOT NULL,
            active boolean NOT NULL DEFAULT true,
            first_seen_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, source_code)
        );
        CREATE INDEX ix_hydro_risk_sectors_geom ON hydro_risk_sectors USING gist (geom);
        CREATE INDEX ix_hydro_risk_sectors_subprefecture ON hydro_risk_sectors (subprefecture);

        CREATE TABLE flood_extent_areas (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            source_code text NOT NULL,
            return_period_years smallint NOT NULL CHECK (return_period_years > 0),
            geom geometry(MultiPolygon, 4326) NOT NULL,
            active boolean NOT NULL DEFAULT true,
            last_seen_at timestamptz NOT NULL,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, source_code)
        );
        CREATE INDEX ix_flood_extent_areas_geom ON flood_extent_areas USING gist (geom);

        CREATE TABLE flood_occurrences (
            id bigserial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            layer text NOT NULL,
            source_code text NOT NULL,
            occurrence_type text NOT NULL CHECK (occurrence_type IN ('ALAGAMENTO','INUNDACAO')),
            occurred_on date NOT NULL,
            subprefecture text,
            geom geometry(Point, 4326) NOT NULL,
            last_seen_at timestamptz NOT NULL,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, layer, source_code)
        );
        CREATE INDEX ix_flood_occurrences_geom ON flood_occurrences USING gist (geom);
        CREATE INDEX ix_flood_occurrences_occurred_on ON flood_occurrences (occurred_on);

        CREATE TABLE risk_runs (
            id bigserial PRIMARY KEY,
            engine_version text NOT NULL,
            computed_at timestamptz NOT NULL,
            valid_until timestamptz NOT NULL,
            forecast_issued_at timestamptz,
            forecast_freshness text NOT NULL,
            status text NOT NULL CHECK (status IN ('SUCCESS','FAILED')),
            sector_count integer NOT NULL DEFAULT 0,
            params jsonb NOT NULL,
            error_summary text
        );
        CREATE INDEX ix_risk_runs_computed_at ON risk_runs (computed_at DESC);

        CREATE TABLE risk_assessments (
            id bigserial PRIMARY KEY,
            run_id bigint NOT NULL REFERENCES risk_runs(id) ON DELETE CASCADE,
            sector_id integer NOT NULL REFERENCES hydro_risk_sectors(id),
            category text NOT NULL CHECK (category IN {CATEGORIES}),
            rain_level smallint CHECK (rain_level BETWEEN 0 AND 3),
            susceptibility smallint NOT NULL CHECK (susceptibility BETWEEN 1 AND 4),
            p1h_max_mm double precision,
            p24_mm double precision,
            a72_mm double precision,
            forecast_point_key text,
            forecast_distance_km double precision,
            in_flood_extent_100y boolean NOT NULL,
            nearby_occurrences_12m integer NOT NULL,
            factors jsonb NOT NULL,
            unknown_reason text,
            UNIQUE (run_id, sector_id)
        );
        CREATE INDEX ix_risk_assessments_sector ON risk_assessments (sector_id)
        """
    )
    _run_each(
        """
        INSERT INTO data_sources (code, name, owner, url, license, attribution, access_method,
                                  expected_interval_s, requires_credentials)
        VALUES
          ('geosampa-risk-sectors', 'GeoSampa — setores de risco hidrológico',
           'Prefeitura de São Paulo', 'https://geosampa.prefeitura.sp.gov.br',
           'Dados abertos municipais (termos de licença não informados nos metadados)',
           'GeoSampa — Prefeitura de São Paulo', 'WFS (GeoJSON), sem chave', 86400, false),
          ('geosampa-flood-extent', 'GeoSampa — manchas de inundação (100 anos)',
           'Prefeitura de São Paulo', 'https://geosampa.prefeitura.sp.gov.br',
           'Dados abertos municipais (termos de licença não informados nos metadados)',
           'GeoSampa — Prefeitura de São Paulo', 'WFS (GeoJSON), sem chave', 86400, false),
          ('geosampa-flood-occurrences', 'GeoSampa — ocorrências de alagamento e inundação',
           'Prefeitura de São Paulo (Defesa Civil/SIGRC)', 'https://geosampa.prefeitura.sp.gov.br',
           'Dados abertos municipais (termos de licença não informados nos metadados)',
           'GeoSampa — Prefeitura de São Paulo', 'WFS (GeoJSON), sem chave', 86400, false),
          ('flood-risk-engine', 'Motor de risco de alagamento v0 (experimental)',
           'Climate Intelligence Platform', 'specs/005-flood-risk-engine',
           'Resultado derivado (DERIVED)', 'Estimativa experimental do sistema',
           'Cálculo interno a partir da previsão e das camadas do GeoSampa', 3600, false)
        """
    )


def downgrade() -> None:
    _run_each(
        """
        DROP TABLE IF EXISTS risk_assessments;
        DROP TABLE IF EXISTS risk_runs;
        DROP TABLE IF EXISTS flood_occurrences;
        DROP TABLE IF EXISTS flood_extent_areas;
        DROP TABLE IF EXISTS hydro_risk_sectors;
        DELETE FROM raw_payloads WHERE source_id IN (
            SELECT id FROM data_sources WHERE code IN ('geosampa-risk-sectors',
            'geosampa-flood-extent', 'geosampa-flood-occurrences', 'flood-risk-engine'));
        DELETE FROM ingestion_runs WHERE source_id IN (
            SELECT id FROM data_sources WHERE code IN ('geosampa-risk-sectors',
            'geosampa-flood-extent', 'geosampa-flood-occurrences', 'flood-risk-engine'));
        DELETE FROM data_sources WHERE code IN ('geosampa-risk-sectors',
            'geosampa-flood-extent', 'geosampa-flood-occurrences', 'flood-risk-engine')
        """
    )

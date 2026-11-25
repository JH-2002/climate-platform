"""Geointeligência (spec 008): hidrografia do GeoSampa, DEM e métricas de terreno.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
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
        CREATE TABLE basins (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            source_code text NOT NULL,
            original_code text,
            name text NOT NULL,
            main_basin text,
            area_km2 double precision,
            coverage text,
            geom geometry(MultiPolygon, 4326) NOT NULL,
            active boolean NOT NULL DEFAULT true,
            last_seen_at timestamptz NOT NULL,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, source_code)
        );
        CREATE INDEX ix_basins_geom ON basins USING gist (geom);

        CREATE TABLE drainage_segments (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            source_code text NOT NULL,
            name text,
            feature_kind text,
            course_type text NOT NULL,
            open_channel boolean NOT NULL,
            length_m double precision,
            geom geometry(MultiLineString, 4326) NOT NULL,
            active boolean NOT NULL DEFAULT true,
            last_seen_at timestamptz NOT NULL,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, source_code)
        );
        CREATE INDEX ix_drainage_geom ON drainage_segments USING gist (geom);

        CREATE TABLE detention_reservoirs (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            source_code text NOT NULL,
            reservoir_code text,
            name text NOT NULL,
            local_basin text,
            main_basin text,
            stream text,
            volume_m3 double precision,
            kind text,
            emptying text,
            manager text,
            realtime_monitoring boolean,
            subprefecture text,
            built text,
            geom geometry(MultiPolygon, 4326) NOT NULL,
            active boolean NOT NULL DEFAULT true,
            last_seen_at timestamptz NOT NULL,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, source_code)
        );
        CREATE INDEX ix_reservoirs_geom ON detention_reservoirs USING gist (geom);

        CREATE TABLE dem_assets (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            kind text NOT NULL CHECK (kind IN ('TILE', 'CLIP')),
            code text NOT NULL,
            etag text,
            bytes bigint NOT NULL,
            sha256 text,
            path text NOT NULL,
            resolution_m double precision,
            bounds jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (kind, code)
        );

        CREATE TABLE sector_terrain (
            sector_id integer PRIMARY KEY REFERENCES hydro_risk_sectors(id) ON DELETE CASCADE,
            computed_at timestamptz NOT NULL,
            dem_sha256 text,
            elev_median_m double precision,
            elev_min_m double precision,
            slope_mean_pct double precision,
            relative_elev_m double precision,
            cells integer NOT NULL,
            low_sample boolean NOT NULL,
            basin_id integer REFERENCES basins(id) ON DELETE SET NULL,
            nearest_drainage_id integer REFERENCES drainage_segments(id) ON DELETE SET NULL,
            nearest_drainage_m double precision
        );

        CREATE TABLE basin_terrain (
            basin_id integer PRIMARY KEY REFERENCES basins(id) ON DELETE CASCADE,
            computed_at timestamptz NOT NULL,
            elev_min_m double precision,
            elev_median_m double precision,
            elev_max_m double precision,
            cells integer NOT NULL
        )
        """
    )
    _run_each(
        """
        INSERT INTO data_sources (code, name, owner, url, license, attribution, access_method,
                                  expected_interval_s, requires_credentials)
        VALUES
          ('copernicus-dem', 'Copernicus DEM GLO-30 — elevação (modelo de superfície, 30 m)',
           'ESA / Copernicus', 'https://copernicus-dem-30m.s3.amazonaws.com',
           'Licença Copernicus DEM (uso livre com atribuição)',
           'Produced using Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence '
           'and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA, '
           'all rights reserved',
           'GeoTIFF otimizado (COG) por HTTPS, download único', 31536000, false),
          ('geosampa-basins', 'GeoSampa — bacias hidrográficas',
           'Prefeitura de São Paulo (SMUL)', 'http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs',
           'Dado público municipal', 'Bacias: GeoSampa — Prefeitura de São Paulo',
           'WFS (GeoJSON), sem token', 2592000, false),
          ('geosampa-drainage', 'GeoSampa — rede de drenagem (rios e córregos)',
           'Prefeitura de São Paulo (SMUL)', 'http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs',
           'Dado público municipal', 'Drenagem: GeoSampa — Prefeitura de São Paulo',
           'WFS (GeoJSON), sem token', 2592000, false),
          ('geosampa-reservoirs', 'GeoSampa — reservatórios de amortecimento (piscinões)',
           'Prefeitura de São Paulo (SMUL)', 'http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs',
           'Dado público municipal', 'Piscinões: GeoSampa — Prefeitura de São Paulo',
           'WFS (GeoJSON), sem token', 2592000, false)
        """
    )


def downgrade() -> None:
    _run_each(
        """
        DROP TABLE IF EXISTS basin_terrain;
        DROP TABLE IF EXISTS sector_terrain;
        DROP TABLE IF EXISTS dem_assets;
        DROP TABLE IF EXISTS detention_reservoirs;
        DROP TABLE IF EXISTS drainage_segments;
        DROP TABLE IF EXISTS basins;
        DELETE FROM raw_payloads WHERE source_id IN (SELECT id FROM data_sources WHERE code IN
            ('copernicus-dem', 'geosampa-basins', 'geosampa-drainage', 'geosampa-reservoirs'));
        DELETE FROM ingestion_runs WHERE source_id IN (SELECT id FROM data_sources WHERE code IN
            ('copernicus-dem', 'geosampa-basins', 'geosampa-drainage', 'geosampa-reservoirs'));
        DELETE FROM data_sources WHERE code IN
            ('copernicus-dem', 'geosampa-basins', 'geosampa-drainage', 'geosampa-reservoirs')
        """
    )

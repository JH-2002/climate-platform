"""Alertas (spec 009): subprefeituras, alertas oficiais (IDAP e INMET) e alertas do sistema.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = "('idap-alerts', 'inmet-warnings', 'geosampa-subprefectures')"


def _run_each(sql: str) -> None:
    """O asyncpg não aceita vários comandos numa execução; envia um por vez."""
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _run_each(
        """
        CREATE TABLE subprefectures (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            source_code text NOT NULL,
            name text NOT NULL,
            acronym text,
            region5 text,
            geom geometry(MultiPolygon, 4326) NOT NULL,
            active boolean NOT NULL DEFAULT true,
            last_seen_at timestamptz NOT NULL,
            raw_payload_id bigint REFERENCES raw_payloads(id),
            UNIQUE (source_id, source_code)
        );
        CREATE INDEX ix_subprefectures_geom ON subprefectures USING gist (geom);

        CREATE TABLE official_alerts (
            id serial PRIMARY KEY,
            source_id integer NOT NULL REFERENCES data_sources(id),
            category text NOT NULL CHECK (category IN ('CIVIL_DEFENSE', 'WEATHER_WARNING')),
            external_id text NOT NULL,
            item_ref text,
            sender_name text,
            msg_type text NOT NULL,
            refs text[] NOT NULL DEFAULT '{}',
            event text,
            severity text,
            urgency text,
            certainty text,
            headline text,
            description text,
            instruction text,
            web text,
            area_desc text,
            color text,
            sent_at timestamptz NOT NULL,
            onset_at timestamptz,
            expires_at timestamptz,
            ended_at timestamptz,
            ended_reason text CHECK (ended_reason IN ('CANCELLED', 'SUPERSEDED')),
            geom geometry(MultiPolygon, 4326),
            area_approximate boolean NOT NULL DEFAULT false,
            city_fraction double precision,
            subprefectures text[] NOT NULL DEFAULT '{}',
            raw_payload_id bigint REFERENCES raw_payloads(id),
            first_seen_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL,
            UNIQUE (source_id, external_id)
        );
        CREATE INDEX ix_official_alerts_time ON official_alerts (expires_at, onset_at);
        CREATE INDEX ix_official_alerts_geom ON official_alerts USING gist (geom);

        CREATE TABLE ignored_alert_items (
            source_id integer NOT NULL REFERENCES data_sources(id),
            item_ref text NOT NULL,
            seen_at timestamptz NOT NULL,
            PRIMARY KEY (source_id, item_ref)
        );

        CREATE TABLE system_alerts (
            id serial PRIMARY KEY,
            rule_code text NOT NULL,
            rules_version text NOT NULL,
            scope_key text NOT NULL,
            scope_label text NOT NULL,
            category text NOT NULL CHECK (category IN ('RISK_ESTIMATE', 'DATA_QUALITY')),
            level text NOT NULL,
            title text NOT NULL,
            message text NOT NULL,
            details jsonb NOT NULL DEFAULT '{}',
            opened_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            closed_at timestamptz,
            clear_count integer NOT NULL DEFAULT 0
        );
        CREATE UNIQUE INDEX ux_system_alerts_open ON system_alerts (rule_code, scope_key)
            WHERE closed_at IS NULL;
        CREATE INDEX ix_system_alerts_opened ON system_alerts (opened_at)
        """
    )
    _run_each(
        """
        INSERT INTO data_sources (code, name, owner, url, license, attribution, access_method,
                                  expected_interval_s, requires_credentials)
        VALUES
          ('idap-alerts', 'Defesa Civil — alertas à população (IDAP)',
           'Ministério da Integração e do Desenvolvimento Regional (SEDEC)',
           'https://idapfile.mdr.gov.br/idap/api/rss/cap',
           'Alerta público oficial', 'Fonte: Defesa Civil (IDAP/MIDR)',
           'Feed Atom com mensagens CAP 1.2, sem cadastro', 600, false),
          ('inmet-warnings', 'INMET — avisos meteorológicos (Alert-AS)',
           'Instituto Nacional de Meteorologia (INMET)',
           'https://apiprevmet3.inmet.gov.br/avisos/rss',
           'Reprodução permitida com citação da fonte', 'Fonte: INMET — Alert-AS',
           'RSS + mensagem CAP 1.2 por aviso, sem cadastro', 1800, false),
          ('geosampa-subprefectures', 'GeoSampa — subprefeituras',
           'Prefeitura de São Paulo (SMUL)',
           'http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs',
           'Dado público municipal', 'Subprefeituras: GeoSampa — Prefeitura de São Paulo',
           'WFS (GeoJSON), sem token', 86400, false)
        """
    )


def downgrade() -> None:
    _run_each(
        f"""
        DROP TABLE IF EXISTS system_alerts;
        DROP TABLE IF EXISTS ignored_alert_items;
        DROP TABLE IF EXISTS official_alerts;
        DROP TABLE IF EXISTS subprefectures;
        DELETE FROM raw_payloads WHERE source_id IN
            (SELECT id FROM data_sources WHERE code IN {_SOURCES});
        DELETE FROM ingestion_runs WHERE source_id IN
            (SELECT id FROM data_sources WHERE code IN {_SOURCES});
        DELETE FROM data_sources WHERE code IN {_SOURCES}
        """
    )

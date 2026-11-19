"""Tabelas do banco (SQLAlchemy Core). A fonte de verdade do DDL são as migrações Alembic;
estas definições espelham o esquema para consultas tipadas.
"""

from __future__ import annotations

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

data_sources = Table(
    "data_sources",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("code", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("owner", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("license", Text, nullable=False),
    Column("attribution", Text, nullable=False),
    Column("access_method", Text, nullable=False),
    Column("expected_interval_s", Integer, nullable=False),
    Column("requires_credentials", Boolean, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("last_attempt_at", DateTime(timezone=True)),
    Column("last_success_at", DateTime(timezone=True)),
    Column("last_status", Text),
    Column("last_error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

weather_stations = Table(
    "weather_stations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("external_code", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("state", Text),
    Column("location", Geography("POINT", srid=4326, spatial_index=False), nullable=False),
    Column("altitude_m", Float),
    Column("status", Text, nullable=False),
    Column("source_status", Text),
    Column("started_at", DateTime(timezone=True)),
    Column("ended_at", DateTime(timezone=True)),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", "external_code"),
)

ingestion_runs = Table(
    "ingestion_runs",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", Text, nullable=False),
    Column("records_received", Integer, nullable=False),
    Column("records_inserted", Integer, nullable=False),
    Column("records_updated", Integer, nullable=False),
    Column("records_rejected", Integer, nullable=False),
    Column("error_summary", Text),
)

raw_payloads = Table(
    "raw_payloads",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("run_id", BigInteger, ForeignKey("ingestion_runs.id"), nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("request_url", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", "content_hash"),
)

weather_observations = Table(
    "weather_observations",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("station_id", Integer, ForeignKey("weather_stations.id"), nullable=False),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("variable", Text, nullable=False),
    Column("value", Float),
    Column("unit", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("mode", Text, nullable=False),
    Column("quality_flag", Text, nullable=False),
    Column("quality_reason", Text),
    Column("raw_payload_id", BigInteger, ForeignKey("raw_payloads.id")),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("station_id", "variable", "observed_at"),
)

weather_forecasts = Table(
    "weather_forecasts",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("point", Geography("POINT", srid=4326, spatial_index=False), nullable=False),
    Column("point_key", Text, nullable=False),
    Column("resolution", Text, nullable=False),
    Column("valid_at", DateTime(timezone=True), nullable=False),
    Column("variable", Text, nullable=False),
    Column("value", Float, nullable=False),
    Column("unit", Text, nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("kind", Text, nullable=False),
    Column("mode", Text, nullable=False),
    Column("raw_payload_id", BigInteger, ForeignKey("raw_payloads.id")),
    UniqueConstraint("source_id", "point_key", "resolution", "variable", "valid_at"),
)

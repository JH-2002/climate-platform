"""Tabelas do banco (SQLAlchemy Core). A fonte de verdade do DDL são as migrações Alembic;
estas definições espelham o esquema para consultas tipadas.
"""

from __future__ import annotations

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

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

# --- spec 005: risco de alagamento ----------------------------------------------------------

hydro_risk_sectors = Table(
    "hydro_risk_sectors",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("source_code", Text, nullable=False),
    Column("area_code", Text),
    Column("area_name", Text),
    Column("grade", SmallInteger, nullable=False),
    Column("processes", ARRAY(Text), nullable=False),
    Column("households", Integer),
    Column("subprefecture", Text),
    Column("basin", Text),
    Column("inspected_on", Date),
    Column("geom", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
    Column("active", Boolean, nullable=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("raw_payload_id", BigInteger, ForeignKey("raw_payloads.id")),
    UniqueConstraint("source_id", "source_code"),
)

flood_extent_areas = Table(
    "flood_extent_areas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("source_code", Text, nullable=False),
    Column("return_period_years", SmallInteger, nullable=False),
    Column("geom", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
    Column("active", Boolean, nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("raw_payload_id", BigInteger, ForeignKey("raw_payloads.id")),
    UniqueConstraint("source_id", "source_code"),
)

flood_occurrences = Table(
    "flood_occurrences",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("layer", Text, nullable=False),
    Column("source_code", Text, nullable=False),
    Column("occurrence_type", Text, nullable=False),
    Column("occurred_on", Date, nullable=False),
    Column("subprefecture", Text),
    Column("geom", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("raw_payload_id", BigInteger, ForeignKey("raw_payloads.id")),
    UniqueConstraint("source_id", "layer", "source_code"),
)

risk_runs = Table(
    "risk_runs",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("engine_version", Text, nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    Column("valid_until", DateTime(timezone=True), nullable=False),
    Column("forecast_issued_at", DateTime(timezone=True)),
    Column("forecast_freshness", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("sector_count", Integer, nullable=False),
    Column("params", JSONB, nullable=False),
    Column("error_summary", Text),
)

risk_assessments = Table(
    "risk_assessments",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("run_id", BigInteger, ForeignKey("risk_runs.id", ondelete="CASCADE"), nullable=False),
    Column("sector_id", Integer, ForeignKey("hydro_risk_sectors.id"), nullable=False),
    Column("category", Text, nullable=False),
    Column("rain_level", SmallInteger),
    Column("susceptibility", SmallInteger, nullable=False),
    Column("p1h_max_mm", Float),
    Column("p24_mm", Float),
    Column("a72_mm", Float),
    Column("forecast_point_key", Text),
    Column("forecast_distance_km", Float),
    Column("in_flood_extent_100y", Boolean, nullable=False),
    Column("nearby_occurrences_12m", Integer, nullable=False),
    Column("factors", JSONB, nullable=False),
    Column("unknown_reason", Text),
    UniqueConstraint("run_id", "sector_id"),
)

# --- spec 006: análises -----------------------------------------------------------------------

climate_daily = Table(
    "climate_daily",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("point_key", Text, nullable=False),
    Column("point", Geography("POINT", srid=4326, spatial_index=False), nullable=False),
    Column("cell_key", Text, nullable=False),
    Column("day", Date, nullable=False),
    Column("variable", Text, nullable=False),
    Column("value", Float, nullable=False),
    Column("unit", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("raw_payload_id", BigInteger, ForeignKey("raw_payloads.id")),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", "point_key", "day", "variable"),
)

rain_monthly_observed = Table(
    "rain_monthly_observed",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("station_code", Text, nullable=False),
    Column("year", SmallInteger, nullable=False),
    Column("month", SmallInteger, nullable=False),
    Column("value_mm", Float, nullable=False),
    Column("kind", Text, nullable=False),
    Column("source_file", Text, nullable=False),
    Column("file_hash", Text, nullable=False),
    Column("imported_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", "station_code", "year", "month"),
)

published_normals = Table(
    "published_normals",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_id", Integer, ForeignKey("data_sources.id"), nullable=False),
    Column("station_code", Text, nullable=False),
    Column("period", Text, nullable=False),
    Column("month", SmallInteger, nullable=False),
    Column("value_mm", Float, nullable=False),
    UniqueConstraint("source_id", "station_code", "period", "month"),
)

backfill_progress = Table(
    "backfill_progress",
    metadata,
    Column("source_id", Integer, ForeignKey("data_sources.id"), primary_key=True),
    Column("point_key", Text, primary_key=True),
    Column("loaded_until", Date),
    Column("completed", Boolean, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

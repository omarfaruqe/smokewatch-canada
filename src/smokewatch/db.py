"""Database engine and schema bootstrap."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from smokewatch.config import settings

SCHEMAS = ("raw",)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def bootstrap(engine: Engine | None = None) -> None:
    """Enable PostGIS and create schemas (safe to run repeatedly)."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        for schema in SCHEMAS:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw._load_log (
                dataset     text        NOT NULL,
                partition   text        NOT NULL,
                sha256      text        NOT NULL,
                row_count   integer     NOT NULL,
                loaded_at   timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (dataset, partition)
            )"""))

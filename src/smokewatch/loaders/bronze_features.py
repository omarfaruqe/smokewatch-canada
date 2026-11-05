"""Load GeoJSON partitions from bronze into Postgres `raw` tables, incrementally.

Every raw table has the same shape, so source schema changes never break the load:

    partition   text         bronze folder, e.g. eccc/climate-hourly/date=2026-11-04
    feature_id  text         source id (uid / id / ID)
    properties  jsonb        all source attributes, untouched
    geom        geometry     EPSG:4326 point (nullable)
    loaded_at   timestamptz

A partition is (re)loaded only when its manifest sha256 differs from `raw._load_log`. A load
deletes the partition's rows and inserts the new ones in one transaction: idempotent, no
duplicates, safe to interrupt.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import Engine, text

from smokewatch.db import bootstrap, get_engine
from smokewatch.storage import BronzeStore

log = logging.getLogger(__name__)

# dataset -> (bronze prefix, raw table)
DATASETS: dict[str, tuple[str, str]] = {
    "hotspots": ("cwfis/hotspots/", "cwfis_hotspots"),
    "aqhi_observations": ("eccc/aqhi-observations-realtime/", "eccc_aqhi_observations"),
    "aqhi_forecasts": ("eccc/aqhi-forecasts-realtime/", "eccc_aqhi_forecasts"),
    "weather": ("eccc/climate-hourly/", "eccc_climate_hourly"),
}


@dataclass
class Partition:
    folder: str
    data_key: str
    manifest_key: str


def find_partitions(store: BronzeStore, prefix: str) -> list[Partition]:
    """Folders under prefix holding a _manifest.json and one .geojson file."""
    keys = store.list(prefix)
    by_folder: dict[str, dict[str, str]] = {}
    for k in keys:
        folder, _, name = k.rpartition("/")
        if name == "_manifest.json":
            by_folder.setdefault(folder, {})["manifest"] = k
        elif name.endswith(".geojson"):
            by_folder.setdefault(folder, {})["data"] = k
    return [
        Partition(f, v["data"], v["manifest"])
        for f, v in sorted(by_folder.items())
        if "data" in v and "manifest" in v
    ]


def feature_id(feature: dict) -> str | None:
    props = feature.get("properties") or {}
    for value in (feature.get("id"), props.get("uid"), props.get("id"), props.get("ID")):
        if value is not None:
            return str(value)
    return None


def to_rows(partition: str, features: list[dict]) -> list[dict]:
    return [
        {
            "partition": partition,
            "feature_id": feature_id(f),
            "properties": json.dumps(f.get("properties") or {}, ensure_ascii=False),
            "geom": json.dumps(f["geometry"]) if f.get("geometry") else None,
        }
        for f in features
    ]


def _ensure_table(conn, table: str) -> None:
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS raw.{table} (
            partition   text        NOT NULL,
            feature_id  text,
            properties  jsonb       NOT NULL,
            geom        geometry(Geometry, 4326),
            loaded_at   timestamptz NOT NULL DEFAULT now()
        )"""))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {table}_partition_idx ON raw.{table} (partition)"))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {table}_geom_idx ON raw.{table} USING gist (geom)"))


def load_dataset(
    store: BronzeStore, dataset: str, engine: Engine | None = None, force: bool = False
) -> dict[str, int]:
    """Load changed partitions of one dataset. Returns {"loaded": n, "skipped": n, "rows": n}."""
    engine = engine or get_engine()
    prefix, table = DATASETS[dataset]
    with engine.begin() as conn:
        _ensure_table(conn, table)
        done = dict(conn.execute(
            text("SELECT partition, sha256 FROM raw._load_log WHERE dataset = :d"), {"d": dataset}
        ).all())

    stats = {"loaded": 0, "skipped": 0, "rows": 0}
    for p in find_partitions(store, prefix):
        sha = json.loads(store.get(p.manifest_key))["sha256"]
        if not force and done.get(p.folder) == sha:
            stats["skipped"] += 1
            continue
        rows = to_rows(p.folder, json.loads(store.get(p.data_key))["features"])
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM raw.{table} WHERE partition = :p"), {"p": p.folder})
            if rows:
                conn.execute(text(f"""
                    INSERT INTO raw.{table} (partition, feature_id, properties, geom)
                    VALUES (:partition, :feature_id, CAST(:properties AS jsonb),
                            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))"""), rows)
            conn.execute(text("""
                INSERT INTO raw._load_log (dataset, partition, sha256, row_count)
                VALUES (:d, :p, :s, :n)
                ON CONFLICT (dataset, partition) DO UPDATE
                SET sha256 = EXCLUDED.sha256, row_count = EXCLUDED.row_count, loaded_at = now()
            """), {"d": dataset, "p": p.folder, "s": sha, "n": len(rows)})
        log.info("%s: loaded %d rows from %s", dataset, len(rows), p.folder)
        stats["loaded"] += 1
        stats["rows"] += len(rows)
    return stats


def load_all(store: BronzeStore, engine: Engine | None = None, force: bool = False) -> dict:
    engine = engine or get_engine()
    bootstrap(engine)
    return {ds: load_dataset(store, ds, engine, force) for ds in DATASETS}

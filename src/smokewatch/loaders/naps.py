"""Load NAPS bronze CSVs into Postgres `raw` (wide station-day rows; unpivoted in dbt).

    raw.naps_hourly    one row per pollutant x method x station x local date, h01..h24 text
    raw.naps_stations  station list (replaced on each load)

Partitions reload only when their manifest sha256 changes (tracked in raw._load_log).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re

import pandas as pd
from sqlalchemy import Engine, text

from smokewatch.db import bootstrap, get_engine
from smokewatch.storage import BronzeStore

log = logging.getLogger(__name__)

HOURLY_COLUMNS = (
    ["pollutant", "method_code", "naps_id", "city", "province", "latitude", "longitude", "date"]
    + [f"h{h:02d}" for h in range(1, 25)]
)


def parse_hourly(data: bytes) -> pd.DataFrame:
    """Skip the bilingual preamble; the table starts at the 'Pollutant//Polluant' header."""
    lines = data.decode("utf-8-sig").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Pollutant//Polluant"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start + 1:])), header=None, dtype=str,
                     names=HOURLY_COLUMNS, keep_default_na=False)
    return df


def _snake(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", name.lower()).strip("_")


def parse_stations(data: bytes) -> pd.DataFrame:
    """The stations CSV has several '*****Section*****' blocks; keep the first data block."""
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    marker = next(i for i, r in enumerate(rows) if r and r[0].startswith("**********Stations"))
    header = [h for h in rows[marker + 1] if h]
    body = []
    for r in rows[marker + 3:]:  # skip the French header row
        if r and r[0].startswith("**********"):
            break
        if r and r[0]:
            body.append(r[:len(header)])
    return pd.DataFrame(body, columns=[_snake(h) for h in header])


def _done(conn, dataset: str) -> dict[str, str]:
    return dict(conn.execute(
        text("SELECT partition, sha256 FROM raw._load_log WHERE dataset = :d"), {"d": dataset}
    ).all())


def _log(conn, dataset: str, partition: str, sha: str, n: int) -> None:
    conn.execute(text("""
        INSERT INTO raw._load_log (dataset, partition, sha256, row_count)
        VALUES (:d, :p, :s, :n)
        ON CONFLICT (dataset, partition) DO UPDATE
        SET sha256 = EXCLUDED.sha256, row_count = EXCLUDED.row_count, loaded_at = now()
    """), {"d": dataset, "p": partition, "s": sha, "n": n})


def load(store: BronzeStore, engine: Engine | None = None, force: bool = False) -> dict:
    engine = engine or get_engine()
    bootstrap(engine)
    stats = {"hourly_partitions": 0, "hourly_rows": 0, "skipped": 0, "stations": 0}

    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS raw.naps_hourly (
                partition text NOT NULL,
                {", ".join(f"{c} text" for c in HOURLY_COLUMNS)},
                loaded_at timestamptz NOT NULL DEFAULT now()
            )"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS naps_hourly_partition_idx "
                          "ON raw.naps_hourly (partition)"))
        done_hourly, done_st = _done(conn, "naps_hourly"), _done(conn, "naps_stations")

    folders = sorted({k.rsplit("/", 1)[0] for k in store.list("naps/hourly/")
                      if k.endswith("_manifest.json")})
    for folder in folders:
        manifest = json.loads(store.get(f"{folder}/_manifest.json"))
        if not force and done_hourly.get(folder) == manifest["sha256"]:
            stats["skipped"] += 1
            continue
        csv_key = next(k for k in store.list(folder + "/") if k.endswith(".csv"))
        df = parse_hourly(store.get(csv_key))
        df.insert(0, "partition", folder)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM raw.naps_hourly WHERE partition = :p"), {"p": folder})
            df.to_sql("naps_hourly", conn, schema="raw", if_exists="append", index=False,
                      method="multi", chunksize=2000)
            _log(conn, "naps_hourly", folder, manifest["sha256"], len(df))
        log.info("loaded %d station-days from %s", len(df), folder)
        stats["hourly_partitions"] += 1
        stats["hourly_rows"] += len(df)

    st_manifest_key = "naps/stations/_manifest.json"
    if store.exists(st_manifest_key):
        sha = json.loads(store.get(st_manifest_key))["sha256"]
        if force or done_st.get("naps/stations") != sha:
            csv_key = next(k for k in store.list("naps/stations/") if k.endswith(".csv"))
            st = parse_stations(store.get(csv_key))
            with engine.begin() as conn:
                st.to_sql("naps_stations", conn, schema="raw", if_exists="replace", index=False)
                _log(conn, "naps_stations", "naps/stations", sha, len(st))
            stats["stations"] = len(st)
    return stats

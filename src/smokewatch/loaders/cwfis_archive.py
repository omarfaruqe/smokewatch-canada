"""Load CWFIS past-season perimeters from bronze into raw.cwfis_season_perimeters.

Keeps the source projection (EPSG:3978, Canada Atlas Lambert); dbt reprojects. Each season
is replaced as a unit and reloaded only when its archive sha256 changes.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
from sqlalchemy import Engine, text

from smokewatch.db import bootstrap, get_engine
from smokewatch.storage import BronzeStore

log = logging.getLogger(__name__)

PREFIX = "cwfis/perimeters_archive/"
TABLE = "cwfis_season_perimeters"


def load(store: BronzeStore, engine: Engine | None = None, force: bool = False) -> dict:
    engine = engine or get_engine()
    bootstrap(engine)
    with engine.connect() as conn:
        done = dict(conn.execute(text(
            "SELECT partition, sha256 FROM raw._load_log WHERE dataset = 'season_perimeters'"
        )).all())
        exists = conn.execute(text("SELECT to_regclass(:t)"), {"t": f"raw.{TABLE}"}).scalar()

    stats = {"seasons_loaded": 0, "skipped": 0, "rows": 0}
    folders = sorted(
        {k.rsplit("/", 1)[0] for k in store.list(PREFIX) if k.endswith("_manifest.json")}
    )
    for folder in folders:
        manifest = json.loads(store.get(f"{folder}/_manifest.json"))
        if not force and done.get(folder) == manifest["sha256"]:
            stats["skipped"] += 1
            continue
        year = int(re.search(r"year=(\d{4})", folder).group(1))
        zip_key = next(k for k in store.list(folder + "/") if k.endswith(".zip"))
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "archive.zip"
            zpath.write_bytes(store.get(zip_key))
            shp = next(n for n in zipfile.ZipFile(zpath).namelist() if n.endswith(".shp"))
            gdf = gpd.read_file(f"zip://{zpath}!{shp}", engine="pyogrio")
        gdf.columns = [c.lower() for c in gdf.columns]
        gdf = gdf.rename_geometry("geom")
        gdf.insert(0, "season_year", year)
        with engine.begin() as conn:
            if exists:
                conn.execute(text(f"DELETE FROM raw.{TABLE} WHERE season_year = :y"), {"y": year})
            gdf.to_postgis(TABLE, conn, schema="raw", if_exists="append", index=False)
            conn.execute(text("""
                INSERT INTO raw._load_log (dataset, partition, sha256, row_count)
                VALUES ('season_perimeters', :p, :s, :n)
                ON CONFLICT (dataset, partition) DO UPDATE
                SET sha256 = EXCLUDED.sha256, row_count = EXCLUDED.row_count, loaded_at = now()
            """), {"p": folder, "s": manifest["sha256"], "n": len(gdf)})
        exists = True
        log.info("loaded %d %s perimeters", len(gdf), year)
        stats["seasons_loaded"] += 1
        stats["rows"] += len(gdf)
    return stats

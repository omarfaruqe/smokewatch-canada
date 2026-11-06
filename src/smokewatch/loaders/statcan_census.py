"""Load StatCan 2021 Census boundaries and population from bronze into Postgres `raw`.

Tables (replaced on every run, so loads are idempotent):
    raw.statcan_census_divisions   293 polygons, EPSG:3347 (StatCan Lambert), full detail
    raw.statcan_provinces          13 polygons, EPSG:3347
    raw.statcan_population_cd      table 98-10-0007-01 (Canada, PR and CD rows)
"""

from __future__ import annotations

import io
import logging
import re
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import Engine, text

from smokewatch.db import bootstrap, get_engine
from smokewatch.extractors.statcan import FILES
from smokewatch.storage import BronzeStore

log = logging.getLogger(__name__)

BOUNDARIES = {
    "census_divisions": ("raw.statcan_census_divisions", "lcd_000b21a_e.shp"),
    "provinces": ("raw.statcan_provinces", "lpr_000b21a_e.shp"),
}


def clean_column(name: str) -> str:
    """'Population and dwelling counts (13): Population, 2021 [1]' -> 'population_2021'."""
    name = name.split("): ", 1)[-1]
    name = re.sub(r"\s*\[\d+\]$", "", name)
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return name


def _load_boundary(store: BronzeStore, engine: Engine, name: str) -> int:
    table, shp = BOUNDARIES[name]
    schema, tbl = table.split(".")
    key = FILES[name][1]
    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / Path(key).name
        zpath.write_bytes(store.get(key))
        gdf = gpd.read_file(f"zip://{zpath}!{shp}", engine="pyogrio")
    gdf.columns = [c.lower() for c in gdf.columns]
    gdf = gdf.rename_geometry("geom")
    if gdf.crs is None or gdf.crs.to_epsg() != 3347:
        gdf = gdf.to_crs(3347)
    gdf.to_postgis(tbl, engine, schema=schema, if_exists="replace", index=False)
    log.info("loaded %d rows into %s", len(gdf), table)
    return len(gdf)


def _load_population(store: BronzeStore, engine: Engine) -> int:
    key = FILES["population_cd"][1]
    with zipfile.ZipFile(io.BytesIO(store.get(key))) as z, z.open("98100007.csv") as f:
        df = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
    df.columns = [clean_column(c) for c in df.columns]
    df.to_sql("statcan_population_cd", engine, schema="raw", if_exists="replace", index=False)
    log.info("loaded %d rows into raw.statcan_population_cd", len(df))
    return len(df)


def load(store: BronzeStore, engine: Engine | None = None) -> dict[str, int]:
    engine = engine or get_engine()
    bootstrap(engine)
    counts = {name: _load_boundary(store, engine, name) for name in BOUNDARIES}
    counts["population_cd"] = _load_population(store, engine)
    with engine.begin() as conn:
        conn.execute(text("ANALYZE raw.statcan_census_divisions"))
        conn.execute(text("ANALYZE raw.statcan_provinces"))
    return counts

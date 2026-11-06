"""SmokeWatch Canada API: read-only access to the wildfire and air-quality marts.

Run:  uvicorn smokewatch.api.main:app --reload     (docs at http://localhost:8000/docs)
"""

from collections.abc import Iterator
from pathlib import Path
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import Connection

from smokewatch import __version__
from smokewatch.api import queries
from smokewatch.db import get_engine

STATIC = Path(__file__).parent / "static"
Province = Literal["NL", "PE", "NS", "NB", "QC", "ON", "MB", "SK", "AB", "BC", "YT", "NT", "NU"]
MAX_RANGE_DAYS = 400

app = FastAPI(
    title="SmokeWatch Canada API",
    version=__version__,
    description=(
        "Wildfires, smoke and population exposure across Canada, built from open data by "
        "Natural Resources Canada, Environment and Climate Change Canada and Statistics "
        "Canada (Open Government Licence - Canada).\n\n"
        "Exposure is estimated per 2021 census division: if any AQHI location in the division "
        "had a high-risk hour (rounded AQHI >= 7) that UTC day, its population counts as "
        "exposed. Treat totals as upper bounds."
    ),
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def get_conn() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn


Conn = Annotated[Connection, Depends(get_conn)]


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    """Bilingual map dashboard (single static page that calls this API)."""
    return FileResponse(STATIC / "index.html")


@app.get("/health", tags=["meta"])
def health(conn: Conn) -> dict:
    """Liveness plus the date range covered by the data."""
    return {"status": "ok", "version": __version__, "coverage": queries.coverage(conn)}


@app.get("/exposure/daily", tags=["exposure"])
def exposure_daily(conn: Conn, start: date, end: date) -> list[dict]:
    """National totals per UTC day: population exposed to high-risk air, hotspots, peak AQHI."""
    if end < start:
        raise HTTPException(422, "end must be on or after start")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(422, f"range is limited to {MAX_RANGE_DAYS} days")
    return queries.national_daily(conn, start, end)


@app.get("/exposure", tags=["exposure"])
def exposure_by_division(conn: Conn, date: date, province: Province | None = None) -> list[dict]:
    """Census divisions for one UTC day, most exposed first."""
    return queries.division_exposure(conn, date, province)


@app.get("/geo/census-divisions", tags=["map"])
def census_divisions_geojson(conn: Conn, date: date) -> dict:
    """All 293 census divisions as GeoJSON (WGS84) with that day's fire and air metrics."""
    return queries.division_geojson(conn, date)


@app.get("/geo/hotspots", tags=["map"])
def hotspots_geojson(
    conn: Conn,
    date: date,
    province: Province | None = None,
    limit: Annotated[int, Query(ge=1, le=50_000)] = 20_000,
) -> dict:
    """Canadian satellite hotspots detected on a UTC day, strongest (FRP) first."""
    return queries.hotspots_geojson(conn, date, province, limit)


@app.get("/geo/fires/season/{year}", tags=["map"])
def season_perimeters(conn: Conn, year: int, province: Province | None = None) -> dict:
    """Final fire perimeters of an archived season (e.g. 2023) as GeoJSON."""
    return queries.season_perimeters_geojson(conn, year, province)


@app.get("/fires/{perimeter_id}/history", tags=["fires"])
def fire_history(conn: Conn, perimeter_id: str) -> list[dict]:
    """SCD Type 2 versions of a current-season fire perimeter (growth over time)."""
    rows = queries.fire_history(conn, perimeter_id)
    if not rows:
        raise HTTPException(404, f"no history for perimeter {perimeter_id!r}")
    return rows


@app.get("/aqhi", tags=["air quality"])
def aqhi(conn: Conn, date: date, cduid: str) -> list[dict]:
    """Hourly AQHI (ECCC observed and NAPS computed) for a census division on a UTC day."""
    return queries.aqhi_hourly(conn, date, cduid)

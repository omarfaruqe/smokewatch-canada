"""SmokeWatch Canada API: read-only access to the wildfire and air-quality marts.

Run:  uvicorn smokewatch.api.main:app --reload     (docs at http://localhost:8000/docs)
"""

import gzip
import logging
import os
import threading
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import Connection

from smokewatch import __version__
from smokewatch.api import queries
from smokewatch.db import get_engine

STATIC = Path(__file__).parent / "static"
log = logging.getLogger(__name__)


class ShapesCache:
    """Census division boundaries, built once per process and kept plain and gzipped.

    Building them takes Postgres several seconds (293 detailed shapes), and they only change
    when the census does, so the first request should not pay that cost. Warmed in the
    background at startup; a request arriving first builds them itself, exactly once.
    Restart the API after restoring a snapshot with new boundaries.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.plain: bytes | None = None
        self.gzipped: bytes | None = None

    def get(self) -> tuple[bytes, bytes]:
        with self._lock:
            if self.plain is None:
                with get_engine().connect() as conn:
                    self.plain = queries.division_shapes_geojson(conn).encode()
                self.gzipped = gzip.compress(self.plain, compresslevel=6)
                log.info("census division shapes cached: %d bytes, %d gzipped",
                         len(self.plain), len(self.gzipped))
            return self.plain, self.gzipped

    def warm(self) -> None:
        try:
            self.get()
        except Exception:  # database not ready yet: the first request will build them
            log.warning("could not warm the shapes cache at startup", exc_info=True)


shapes_cache = ShapesCache()


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=shapes_cache.warm, daemon=True).start()
    yield
Province = Literal["NL", "PE", "NS", "NB", "QC", "ON", "MB", "SK", "AB", "BC", "YT", "NT", "NU"]
MAX_RANGE_DAYS = 400

app = FastAPI(
    lifespan=lifespan,
    # Set API_ROOT_PATH=/smokewatch when served under that path by a reverse proxy, so the
    # interactive docs load their OpenAPI schema from the right URL.
    root_path=os.getenv("API_ROOT_PATH", ""),
    title="SmokeWatch Canada API",
    version=__version__,
    description=(
        "Wildfires, smoke and population exposure across Canada, built from open data by "
        "Natural Resources Canada, Environment and Climate Change Canada and Statistics "
        "Canada (Open Government Licence - Canada).\n\n"
        "Two exposure estimates are provided. `population_exposed_high_risk` "
        "(whole-division count): a 2021 census division's whole population counts once any of "
        "its AQHI locations has a "
        "high-risk hour (rounded AQHI >= 7) that UTC day. `population_exposed_high_risk_da` "
        "(nearest station): each 2021 dissemination area counts when its nearest AQHI "
        "location within 50 km has a high-risk hour; `population_aqhi_covered_da` is the "
        "population within range of a location."
    ),
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)  # GeoJSON compresses several-fold

GEOJSON = "application/geo+json"
SHAPES_CACHE_SECONDS = 86_400  # boundaries change only when the census does


def geojson(body: str, cache_seconds: int | None = None) -> Response:
    headers = {"Cache-Control": f"public, max-age={cache_seconds}"} if cache_seconds else None
    return Response(content=body, media_type=GEOJSON, headers=headers)

# Data only changes when the pipeline reloads, and replaying a season revisits the same days,
# so data responses may be cached briefly. Health responses must always be fresh.
CACHE_SECONDS = int(os.getenv("API_CACHE_SECONDS", "300"))


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.method == "GET" and response.status_code == 200:
        if request.url.path.startswith("/health"):
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers.setdefault("Cache-Control", f"public, max-age={CACHE_SECONDS}")
    return response


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


@app.get("/health/pipeline", tags=["meta"])
def pipeline_health(conn: Conn) -> list[dict]:
    """Per dataset: partitions and rows loaded, last load time, and latest observation."""
    return queries.pipeline_health(conn)


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


@app.get("/geo/census-divisions/shapes", tags=["map"], response_class=Response)
def census_division_shapes(request: Request) -> Response:
    """All 293 census division boundaries (WGS84) with static attributes, cached for a day.
    Load once and colour by day with GET /exposure?date=, instead of re-downloading shapes."""
    plain, gzipped = shapes_cache.get()
    headers = {
        "Cache-Control": f"public, max-age={SHAPES_CACHE_SECONDS}",
        "Vary": "Accept-Encoding",
    }
    if "gzip" in request.headers.get("accept-encoding", ""):
        headers["Content-Encoding"] = "gzip"
        return Response(content=gzipped, media_type=GEOJSON, headers=headers)
    return Response(content=plain, media_type=GEOJSON, headers=headers)


@app.get("/geo/census-divisions", tags=["map"], response_class=Response)
def census_divisions_geojson(conn: Conn, date: date) -> Response:
    """All 293 census divisions as GeoJSON (WGS84) with that day's fire and air metrics."""
    return geojson(queries.division_geojson(conn, date))


@app.get("/geo/hotspots", tags=["map"], response_class=Response)
def hotspots_geojson(
    conn: Conn,
    date: date,
    province: Province | None = None,
    limit: Annotated[int, Query(ge=1, le=50_000)] = 20_000,
) -> Response:
    """Canadian satellite hotspots detected on a UTC day, strongest (FRP) first."""
    return geojson(queries.hotspots_geojson(conn, date, province, limit))


@app.get("/geo/fires/season/{year}", tags=["map"], response_class=Response)
def season_perimeters(conn: Conn, year: int, province: Province | None = None) -> Response:
    """Final fire perimeters of an archived season (e.g. 2023) as GeoJSON."""
    return geojson(queries.season_perimeters_geojson(conn, year, province))


@app.get("/fires/{perimeter_id}/history", tags=["fires"])
def fire_history(conn: Conn, perimeter_id: str) -> list[dict]:
    """SCD Type 2 versions of a current-season fire perimeter (growth over time)."""
    rows = queries.fire_history(conn, perimeter_id)
    if not rows:
        raise HTTPException(404, f"no history for perimeter {perimeter_id!r}")
    return rows


@app.get("/aqhi/forecast-skill", tags=["air quality"])
def forecast_skill(conn: Conn) -> list[dict]:
    """Accuracy of ECCC hourly AQHI forecasts by lead time: MAE, bias, share within 1 point,
    probability of detection (pod) and false alarm ratio (far) for high-risk hours."""
    return queries.forecast_skill(conn)


@app.get("/aqhi", tags=["air quality"])
def aqhi(conn: Conn, date: date, cduid: str) -> list[dict]:
    """Hourly AQHI (ECCC observed and NAPS computed) for a census division on a UTC day."""
    return queries.aqhi_hourly(conn, date, cduid)

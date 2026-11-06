"""Extract satellite fire hotspots from the CWFIS GeoServer (Natural Resources Canada).

Bronze layout (one object per day, overwritten on re-run, so loads are idempotent):

    cwfis/hotspots/<layer>/date=YYYY-MM-DD/hotspots.geojson
    cwfis/hotspots/<layer>/date=YYYY-MM-DD/_manifest.json

Layers:
    public:hotspots_24h  - rolling last 24 hours (used for the daily run)
    public:hotspots      - full season, filtered by rep_date (used for backfill)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import requests

from smokewatch.config import settings
from smokewatch.storage import BronzeStore, put_json

log = logging.getLogger(__name__)

LAYER_24H = "public:hotspots_24h"
LAYER_ALL = "public:hotspots"
PAGE_SIZE = 10_000
MAX_RETRIES = 4


@dataclass
class ExtractResult:
    layer: str
    day: date
    feature_count: int
    data_key: str
    manifest_key: str
    sha256: str


def bronze_prefix(layer: str, day: date) -> str:
    short = layer.split(":")[-1]
    return f"cwfis/hotspots/{short}/date={day.isoformat()}"


def day_filter(day: date) -> str:
    """CQL filter selecting hotspots reported on one UTC day."""
    nxt = day + timedelta(days=1)
    return f"rep_date >= '{day.isoformat()}T00:00:00Z' AND rep_date < '{nxt.isoformat()}T00:00:00Z'"


def _get_with_retry(session: requests.Session, url: str, params: dict) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == MAX_RETRIES:
                raise
            wait = 2**attempt
            log.warning("CWFIS request failed (%s), retry %d in %ds", exc, attempt, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def fetch_features(
    layer: str,
    cql_filter: str | None = None,
    session: requests.Session | None = None,
    page_size: int = PAGE_SIZE,
    sort_by: str | None = "rep_date",
) -> list[dict]:
    """Page through a WFS layer and return all GeoJSON features (sorted for stable paging)."""
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", settings.user_agent)
    features: list[dict] = []
    start = 0
    while True:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": page_size,
            "startIndex": start,
        }
        if sort_by:
            params["sortBy"] = sort_by
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        page = _get_with_retry(session, settings.cwfis_wfs_url, params)
        batch = page.get("features", [])
        features.extend(batch)
        log.info("fetched %d features (startIndex=%d)", len(batch), start)
        if len(batch) < page_size:
            return features
        start += page_size


def extract(
    store: BronzeStore,
    day: date | None = None,
    session: requests.Session | None = None,
) -> ExtractResult:
    """Extract one day of hotspots into bronze.

    day=None -> rolling last-24h layer, stored under today's UTC date.
    day=...  -> full layer filtered to that rep_date (backfill).
    """
    if day is None:
        layer, cql = LAYER_24H, None
        day = datetime.now(timezone.utc).date()
    else:
        layer, cql = LAYER_ALL, day_filter(day)

    features = fetch_features(layer, cql, session=session)
    collection = {"type": "FeatureCollection", "features": features}
    payload = json.dumps(collection, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()

    prefix = bronze_prefix(layer, day)
    data_key = f"{prefix}/hotspots.geojson"
    manifest_key = f"{prefix}/_manifest.json"

    store.put(data_key, payload, content_type="application/geo+json")
    put_json(
        store,
        manifest_key,
        {
            "source": "CWFIS (Natural Resources Canada)",
            "endpoint": settings.cwfis_wfs_url,
            "layer": layer,
            "cql_filter": cql,
            "partition_date": day.isoformat(),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "feature_count": len(features),
            "sha256": digest,
            "licence": "Open Government Licence - Canada",
        },
    )
    log.info("wrote %d hotspots to %s", len(features), data_key)
    return ExtractResult(layer, day, len(features), data_key, manifest_key, digest)


def backfill(
    store: BronzeStore,
    start: date,
    end: date,
    session: requests.Session | None = None,
    skip_existing: bool = True,
) -> list[ExtractResult]:
    """Extract every day in [start, end]; skips days already in bronze unless told not to."""
    results = []
    day = start
    while day <= end:
        manifest = f"{bronze_prefix(LAYER_ALL, day)}/_manifest.json"
        if skip_existing and store.exists(manifest):
            log.info("skip %s (already in bronze)", day)
        else:
            results.append(extract(store, day, session=session))
        day += timedelta(days=1)
    return results

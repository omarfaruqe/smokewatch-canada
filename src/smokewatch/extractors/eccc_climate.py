"""Extract hourly weather observations (ECCC `climate-hourly`) for all stations in Canada.

Bronze layout (one object per UTC day, overwritten on re-run):
    eccc/climate-hourly/date=YYYY-MM-DD/{items.geojson,_manifest.json}

The day is selected with exact property filters (UTC_YEAR, UTC_MONTH, UTC_DAY), so the
partition matches UTC days regardless of how the server's temporal filter is configured.
The archive is published with a lag, so the default day is yesterday (UTC).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import requests

from smokewatch.extractors.common import PartitionResult, write_feature_partition
from smokewatch.extractors.eccc_ogc import fetch_items, items_url
from smokewatch.storage import BronzeStore

COLLECTION = "climate-hourly"


def day_params(day: date) -> dict:
    return {"UTC_YEAR": day.year, "UTC_MONTH": day.month, "UTC_DAY": day.day}


def prefix_for(day: date) -> str:
    return f"eccc/{COLLECTION}/date={day.isoformat()}"


def hourly(
    store: BronzeStore, day: date | None = None, session: requests.Session | None = None
) -> PartitionResult:
    day = day or (datetime.now(timezone.utc).date() - timedelta(days=1))
    params = day_params(day)
    features = fetch_items(COLLECTION, params, session=session)
    return write_feature_partition(
        store,
        prefix_for(day),
        features,
        {"source": "ECCC MSC GeoMet", "endpoint": items_url(COLLECTION), "params": params,
         "partition_date": day.isoformat()},
    )


def hourly_range(
    store: BronzeStore, start: date, end: date, session: requests.Session | None = None,
    skip_existing: bool = True,
) -> list[PartitionResult]:
    results, day = [], start
    while day <= end:
        if not (skip_existing and store.exists(f"{prefix_for(day)}/_manifest.json")):
            results.append(hourly(store, day, session=session))
        day += timedelta(days=1)
    return results

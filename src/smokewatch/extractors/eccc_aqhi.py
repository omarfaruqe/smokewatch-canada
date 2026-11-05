"""Extract Air Quality Health Index (AQHI) data from ECCC MSC GeoMet.

Bronze layout:
    eccc/aqhi-observations-realtime/date=YYYY-MM-DD/{items.geojson,_manifest.json}
        one object per UTC day of hourly observations (re-run overwrites)
    eccc/aqhi-forecasts-realtime/pub_date=YYYY-MM-DD/{items.geojson,_manifest.json}
        forecasts grouped by publication date. The API serves a rolling ~3-day window of
        publications, so each run merges into the existing partition by feature id
        (new wins). Re-runs are idempotent and rows that aged out of the window are kept.

Observations get late amendments, so the daily job should also re-pull yesterday.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import requests

from smokewatch.extractors.common import PartitionResult, write_feature_partition
from smokewatch.extractors.eccc_ogc import day_interval, fetch_items, items_url
from smokewatch.storage import BronzeStore

OBS = "aqhi-observations-realtime"
FCST = "aqhi-forecasts-realtime"


def observations(
    store: BronzeStore, day: date | None = None, session: requests.Session | None = None
) -> PartitionResult:
    day = day or datetime.now(timezone.utc).date()
    params = {"datetime": day_interval(day)}
    features = fetch_items(OBS, params, session=session)
    return write_feature_partition(
        store,
        f"eccc/{OBS}/date={day.isoformat()}",
        features,
        {"source": "ECCC MSC GeoMet", "endpoint": items_url(OBS), "params": params,
         "partition_date": day.isoformat()},
    )


def _merge_by_id(existing: list[dict], new: list[dict]) -> list[dict]:
    merged = {f.get("id") or f["properties"]["id"]: f for f in existing}
    merged.update({f.get("id") or f["properties"]["id"]: f for f in new})
    return sorted(merged.values(), key=lambda f: f.get("id") or f["properties"]["id"])


def forecasts(
    store: BronzeStore, session: requests.Session | None = None
) -> list[PartitionResult]:
    """Fetch the forecast window and merge it into per-publication-date partitions."""
    features = fetch_items(FCST, session=session)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for f in features:
        by_day[f["properties"]["publication_datetime"][:10]].append(f)

    results = []
    for day, feats in sorted(by_day.items()):
        prefix = f"eccc/{FCST}/pub_date={day}"
        data_key = f"{prefix}/items.geojson"
        if store.exists(data_key):
            feats = _merge_by_id(json.loads(store.get(data_key))["features"], feats)
        results.append(
            write_feature_partition(
                store, prefix, feats,
                {"source": "ECCC MSC GeoMet", "endpoint": items_url(FCST),
                 "partition_pub_date": day, "merge_key": "id"},
            )
        )
    return results


def observations_range(
    store: BronzeStore, start: date, end: date, session: requests.Session | None = None,
    skip_existing: bool = True,
) -> list[PartitionResult]:
    results, day = [], start
    while day <= end:
        if not (skip_existing and store.exists(f"eccc/{OBS}/date={day.isoformat()}/_manifest.json")):
            results.append(observations(store, day, session=session))
        day += timedelta(days=1)
    return results

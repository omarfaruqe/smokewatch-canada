"""Extract Air Quality Health Index (AQHI) data from ECCC MSC GeoMet.

Bronze layout:
    eccc/aqhi-observations-realtime/date=YYYY-MM-DD/{items.geojson,_manifest.json}
        one object per UTC day of hourly observations (re-run overwrites)
    eccc/aqhi-forecasts-realtime/date=YYYY-MM-DD/hour=HH/{items.geojson,_manifest.json}
        snapshot of the current forecasts, one per fetch hour (forecasts are re-issued
        through the day, so each snapshot is kept)
"""

from __future__ import annotations

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


def forecasts(
    store: BronzeStore, now: datetime | None = None, session: requests.Session | None = None
) -> PartitionResult:
    now = now or datetime.now(timezone.utc)
    features = fetch_items(FCST, session=session)
    return write_feature_partition(
        store,
        f"eccc/{FCST}/date={now.date().isoformat()}/hour={now.hour:02d}",
        features,
        {"source": "ECCC MSC GeoMet", "endpoint": items_url(FCST),
         "snapshot_utc": now.isoformat(timespec="seconds")},
    )


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

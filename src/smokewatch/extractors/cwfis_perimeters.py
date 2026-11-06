"""Snapshot CWFIS current fire perimeters (M3 hotspot-derived polygons) into bronze.

The layer only exposes the current state, so history comes from one snapshot per UTC day:
    cwfis/perimeters/m3_polygons_current/date=YYYY-MM-DD/{items.geojson,_manifest.json}
Re-running the same day overwrites that day's snapshot (idempotent). dbt derives SCD Type 2
history from the sequence of daily snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone

import requests

from smokewatch.config import settings
from smokewatch.extractors.common import PartitionResult, write_feature_partition
from smokewatch.extractors.cwfis_hotspots import fetch_features

LAYER = "public:m3_polygons_current"


def snapshot(store, session: requests.Session | None = None, now: datetime | None = None
             ) -> PartitionResult:
    now = now or datetime.now(timezone.utc)
    features = fetch_features(LAYER, session=session, sort_by="lastdate")
    return write_feature_partition(
        store,
        f"cwfis/perimeters/m3_polygons_current/date={now.date().isoformat()}",
        features,
        {"source": "CWFIS (Natural Resources Canada)", "endpoint": settings.cwfis_wfs_url,
         "layer": LAYER, "snapshot_utc": now.isoformat(timespec="seconds")},
    )

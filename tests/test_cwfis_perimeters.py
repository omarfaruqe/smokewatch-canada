"""Offline test for the fire-perimeter snapshot (no network)."""

import json
from datetime import datetime, timezone

from smokewatch.extractors import cwfis_perimeters
from smokewatch.storage import LocalStore


class FakeResponse:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class FakeWFS:
    def __init__(self):
        self.headers, self.calls = {}, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        feats = [{"type": "Feature", "id": "m3_polygons_current.1",
                  "geometry": {"type": "Polygon",
                               "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                  "properties": {"hcount": 5, "area": 12.5}}]
        return FakeResponse({"type": "FeatureCollection", "features": feats})


def test_snapshot_partitioned_by_utc_day(tmp_path):
    store = LocalStore(tmp_path)
    s = FakeWFS()
    now = datetime(2026, 11, 5, 21, 0, tzinfo=timezone.utc)
    r = cwfis_perimeters.snapshot(store, session=s, now=now)
    assert r.prefix == "cwfis/perimeters/m3_polygons_current/date=2026-11-05"
    assert s.calls[0]["typeNames"] == "public:m3_polygons_current"
    assert s.calls[0]["sortBy"] == "lastdate"
    assert json.loads(store.get(r.manifest_key))["feature_count"] == 1

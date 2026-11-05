"""Offline tests for the ECCC OGC client and AQHI extractor (no network)."""

import json
from datetime import date, datetime, timezone

from smokewatch.extractors import eccc_aqhi
from smokewatch.extractors.eccc_ogc import day_interval, fetch_items
from smokewatch.storage import LocalStore


class FakeResponse:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class FakeOGC:
    """Serves `total` features in pages of `size`, linking pages with rel=next."""

    def __init__(self, total, size=4):
        self.total, self.size = total, size
        self.headers, self.calls = {}, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        offset = int(url.split("offset=")[1]) if "offset=" in url else 0
        feats = [
            {"type": "Feature", "geometry": None, "properties": {"n": i}}
            for i in range(offset, min(offset + self.size, self.total))
        ]
        links = []
        if offset + self.size < self.total:
            links.append({"rel": "next", "href": f"https://x/items?offset={offset + self.size}"})
        return FakeResponse({"type": "FeatureCollection", "features": feats, "links": links})


def test_day_interval():
    assert day_interval(date(2026, 8, 15)) == "2026-08-15T00:00:00Z/2026-08-15T23:59:59Z"


def test_follows_next_links():
    s = FakeOGC(total=10, size=4)
    feats = fetch_items("aqhi-observations-realtime", {"datetime": "x"}, session=s)
    assert [f["properties"]["n"] for f in feats] == list(range(10))
    assert len(s.calls) == 3
    assert s.calls[0][1]["datetime"] == "x" and s.calls[1][1] is None


def test_observations_partition(tmp_path):
    store = LocalStore(tmp_path)
    r = eccc_aqhi.observations(store, date(2026, 8, 15), session=FakeOGC(total=6))
    assert r.data_key == "eccc/aqhi-observations-realtime/date=2026-08-15/items.geojson"
    m = json.loads(store.get(r.manifest_key))
    assert m["feature_count"] == 6 and m["params"]["datetime"].startswith("2026-08-15")


def test_forecast_snapshot_keyed_by_hour(tmp_path):
    store = LocalStore(tmp_path)
    now = datetime(2026, 11, 5, 14, 30, tzinfo=timezone.utc)
    r = eccc_aqhi.forecasts(store, now=now, session=FakeOGC(total=3))
    assert r.prefix == "eccc/aqhi-forecasts-realtime/date=2026-11-05/hour=14"


def test_observations_range_skips_existing(tmp_path):
    store = LocalStore(tmp_path)
    eccc_aqhi.observations(store, date(2026, 8, 1), session=FakeOGC(total=1))
    rs = eccc_aqhi.observations_range(
        store, date(2026, 8, 1), date(2026, 8, 2), session=FakeOGC(total=1)
    )
    assert [r.prefix[-10:] for r in rs] == ["2026-08-02"]

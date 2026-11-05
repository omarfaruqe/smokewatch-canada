"""Offline tests for the ECCC climate-hourly extractor (no network)."""

import json
from datetime import date

from smokewatch.extractors import eccc_climate
from smokewatch.storage import LocalStore


class FakeResponse:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class FakeClimate:
    def __init__(self, n=3):
        self.n, self.headers, self.calls = n, {}, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        feats = [{"type": "Feature", "id": f"s.{i}", "geometry": None,
                  "properties": {"ID": f"s.{i}", "TEMP": 10 + i}} for i in range(self.n)]
        return FakeResponse({"type": "FeatureCollection", "features": feats, "links": []})


def test_day_params_are_exact_utc_day():
    assert eccc_climate.day_params(date(2026, 8, 5)) == {
        "UTC_YEAR": 2026, "UTC_MONTH": 8, "UTC_DAY": 5}


def test_hourly_writes_partition_with_filters(tmp_path):
    store = LocalStore(tmp_path)
    s = FakeClimate(n=3)
    r = eccc_climate.hourly(store, date(2026, 8, 5), session=s)
    assert r.data_key == "eccc/climate-hourly/date=2026-08-05/items.geojson"
    assert s.calls[0]["UTC_DAY"] == 5 and s.calls[0]["f"] == "json"
    assert json.loads(store.get(r.manifest_key))["feature_count"] == 3


def test_hourly_range_skips_existing(tmp_path):
    store = LocalStore(tmp_path)
    eccc_climate.hourly(store, date(2026, 8, 5), session=FakeClimate())
    rs = eccc_climate.hourly_range(store, date(2026, 8, 5), date(2026, 8, 6),
                                   session=FakeClimate())
    assert [r.prefix[-10:] for r in rs] == ["2026-08-06"]

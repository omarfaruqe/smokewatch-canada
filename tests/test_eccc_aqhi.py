"""Offline tests for the ECCC OGC client and AQHI extractor (no network)."""

import json
from datetime import date

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


class FakeForecasts(FakeOGC):
    """Single page of forecasts with given (id, publication_datetime, aqhi) rows."""

    def __init__(self, rows):
        super().__init__(total=0)
        self.rows = rows

    def get(self, url, params=None, timeout=None):
        feats = [
            {"type": "Feature", "id": i, "geometry": None,
             "properties": {"id": i, "publication_datetime": pub, "aqhi": a}}
            for i, pub, a in self.rows
        ]
        return FakeResponse({"type": "FeatureCollection", "features": feats, "links": []})


def test_forecasts_partitioned_by_publication_date(tmp_path):
    store = LocalStore(tmp_path)
    rs = eccc_aqhi.forecasts(store, session=FakeForecasts(
        [("a", "2026-11-03T11:00:00Z", 2), ("b", "2026-11-04T11:00:00Z", 3)]))
    assert [r.prefix for r in rs] == [
        "eccc/aqhi-forecasts-realtime/pub_date=2026-11-03",
        "eccc/aqhi-forecasts-realtime/pub_date=2026-11-04",
    ]


def test_forecasts_merge_keeps_aged_out_rows_and_updates(tmp_path):
    store = LocalStore(tmp_path)
    eccc_aqhi.forecasts(store, session=FakeForecasts(
        [("a", "2026-11-03T00:00:00Z", 2), ("b", "2026-11-03T11:00:00Z", 3)]))
    # next run: "a" aged out of the API window, "b" amended, "c" new
    eccc_aqhi.forecasts(store, session=FakeForecasts(
        [("b", "2026-11-03T11:00:00Z", 5), ("c", "2026-11-03T12:00:00Z", 1)]))
    key = "eccc/aqhi-forecasts-realtime/pub_date=2026-11-03/items.geojson"
    feats = {f["id"]: f["properties"]["aqhi"] for f in json.loads(store.get(key))["features"]}
    assert feats == {"a": 2, "b": 5, "c": 1}


def test_forecasts_rerun_is_idempotent(tmp_path):
    store = LocalStore(tmp_path)
    rows = [("a", "2026-11-03T00:00:00Z", 2)]
    r1 = eccc_aqhi.forecasts(store, session=FakeForecasts(rows))[0]
    r2 = eccc_aqhi.forecasts(store, session=FakeForecasts(rows))[0]
    assert r1.sha256 == r2.sha256


def test_observations_range_skips_existing(tmp_path):
    store = LocalStore(tmp_path)
    eccc_aqhi.observations(store, date(2026, 8, 1), session=FakeOGC(total=1))
    rs = eccc_aqhi.observations_range(
        store, date(2026, 8, 1), date(2026, 8, 2), session=FakeOGC(total=1)
    )
    assert [r.prefix[-10:] for r in rs] == ["2026-08-02"]

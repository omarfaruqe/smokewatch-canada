"""Offline tests for the CWFIS hotspot extractor (no network)."""

import json
from datetime import date

from smokewatch.extractors import cwfis_hotspots as cw
from smokewatch.storage import LocalStore


def _feature(i: int) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-75.0 - i * 0.01, 50.0]},
        "properties": {"rep_date": "2026-07-01T18:00:00Z", "id": i},
    }


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Serves `total` features in pages, recording every request's params."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.headers: dict = {}
        self.calls: list[dict] = []

    def get(self, url, params, timeout):
        self.calls.append(dict(params))
        start, count = params["startIndex"], params["count"]
        feats = [_feature(i) for i in range(start, min(start + count, self.total))]
        return FakeResponse({"type": "FeatureCollection", "features": feats})


def test_bronze_prefix_and_filter():
    d = date(2023, 6, 7)
    assert cw.bronze_prefix(cw.LAYER_ALL, d) == "cwfis/hotspots/hotspots/date=2023-06-07"
    assert "2023-06-07T00:00:00Z" in cw.day_filter(d)
    assert "2023-06-08T00:00:00Z" in cw.day_filter(d)


def test_pagination_collects_all_pages():
    s = FakeSession(total=25)
    feats = cw.fetch_features(cw.LAYER_ALL, session=s, page_size=10)
    assert len(feats) == 25
    assert [c["startIndex"] for c in s.calls] == [0, 10, 20]


def test_extract_writes_data_and_manifest(tmp_path):
    store = LocalStore(tmp_path)
    r = cw.extract(store, date(2023, 6, 7), session=FakeSession(total=3))
    assert r.feature_count == 3
    data = json.loads(store.get(r.data_key))
    manifest = json.loads(store.get(r.manifest_key))
    assert data["type"] == "FeatureCollection" and len(data["features"]) == 3
    assert manifest["feature_count"] == 3 and manifest["sha256"] == r.sha256
    assert manifest["layer"] == cw.LAYER_ALL


def test_extract_is_idempotent(tmp_path):
    store = LocalStore(tmp_path)
    a = cw.extract(store, date(2023, 6, 7), session=FakeSession(total=5))
    b = cw.extract(store, date(2023, 6, 7), session=FakeSession(total=5))
    assert a.data_key == b.data_key and a.sha256 == b.sha256
    assert len(list(tmp_path.rglob("hotspots.geojson"))) == 1


def test_backfill_skips_existing_days(tmp_path):
    store = LocalStore(tmp_path)
    cw.extract(store, date(2023, 6, 1), session=FakeSession(total=2))
    results = cw.backfill(store, date(2023, 6, 1), date(2023, 6, 3), session=FakeSession(total=2))
    assert [r.day for r in results] == [date(2023, 6, 2), date(2023, 6, 3)]


def test_fetch_features_sort_is_optional():
    s = FakeSession(total=2)
    cw.fetch_features(cw.LAYER_ALL, session=s, sort_by=None)
    assert "sortBy" not in s.calls[0]
    cw.fetch_features(cw.LAYER_ALL, session=s)
    assert s.calls[-1]["sortBy"] == "rep_date"

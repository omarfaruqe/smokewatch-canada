"""Pure-function tests for the bronze -> raw feature loader (no database)."""

import json

import pytest

pytest.importorskip("sqlalchemy")

from smokewatch.loaders.bronze_features import feature_id, find_partitions, to_rows  # noqa: E402
from smokewatch.storage import LocalStore  # noqa: E402


def test_find_partitions_requires_manifest_and_data(tmp_path):
    store = LocalStore(tmp_path)
    store.put("eccc/x/date=2026-11-04/items.geojson", b"{}")
    store.put("eccc/x/date=2026-11-04/_manifest.json", b"{}")
    store.put("eccc/x/date=2026-11-05/items.geojson", b"{}")  # no manifest -> ignored
    store.put("cwfis/hotspots/h/date=2026-11-05/hotspots.geojson", b"{}")
    store.put("cwfis/hotspots/h/date=2026-11-05/_manifest.json", b"{}")
    assert [p.folder for p in find_partitions(store, "eccc/x/")] == ["eccc/x/date=2026-11-04"]
    [p] = find_partitions(store, "cwfis/hotspots/")
    assert p.data_key.endswith("hotspots.geojson")


@pytest.mark.parametrize("feat,expected", [
    ({"id": "AQ_OBS-1", "properties": {}}, "AQ_OBS-1"),
    ({"properties": {"uid": 32618647}}, "32618647"),
    ({"properties": {"ID": "1017101.2024.10.4.3"}}, "1017101.2024.10.4.3"),
    ({"properties": {}}, None),
])
def test_feature_id(feat, expected):
    assert feature_id(feat) == expected


def test_to_rows_keeps_properties_and_geometry():
    f = {"id": "a", "geometry": {"type": "Point", "coordinates": [-75, 45]},
         "properties": {"aqhi": 3, "name": "Montréal"}}
    [row] = to_rows("p", [f, ])
    assert json.loads(row["properties"]) == {"aqhi": 3, "name": "Montréal"}
    assert json.loads(row["geom"])["coordinates"] == [-75, 45]
    assert to_rows("p", [{"properties": {}}])[0]["geom"] is None

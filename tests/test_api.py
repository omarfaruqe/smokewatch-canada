"""API wiring and validation tests; queries are replaced with fakes (no database)."""

from datetime import date

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from smokewatch.api import main, queries  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    main.app.dependency_overrides[main.get_conn] = lambda: None
    calls = {}

    def fake(name, result):
        def _f(conn, *args):
            calls[name] = args
            return result
        monkeypatch.setattr(queries, name, _f)

    fake("national_daily", [{"day": "2023-06-07", "population_exposed_high_risk": 1}])
    fake("division_exposure", [{"cduid": "2466"}])
    fake("hotspots_geojson", {"type": "FeatureCollection", "features": []})
    fake("fire_history", [])
    yield TestClient(main.app), calls
    main.app.dependency_overrides.clear()


def test_daily_exposure_passes_dates(client):
    c, calls = client
    r = c.get("/exposure/daily", params={"start": "2023-06-01", "end": "2023-06-30"})
    assert r.status_code == 200 and r.json()[0]["population_exposed_high_risk"] == 1
    assert calls["national_daily"] == (date(2023, 6, 1), date(2023, 6, 30))


@pytest.mark.parametrize("start,end,msg", [
    ("2023-06-30", "2023-06-01", "end must be on or after start"),
    ("2022-01-01", "2023-12-31", "limited to"),
])
def test_daily_exposure_rejects_bad_ranges(client, start, end, msg):
    c, _ = client
    r = c.get("/exposure/daily", params={"start": start, "end": end})
    assert r.status_code == 422 and msg in r.text


def test_province_must_be_valid_code(client):
    c, calls = client
    assert c.get("/exposure", params={"date": "2023-06-07", "province": "QC"}).status_code == 200
    assert calls["division_exposure"] == (date(2023, 6, 7), "QC")
    assert c.get("/exposure", params={"date": "2023-06-07", "province": "XX"}).status_code == 422


def test_hotspot_limit_bounds(client):
    c, calls = client
    assert c.get("/geo/hotspots", params={"date": "2023-06-07"}).status_code == 200
    assert calls["hotspots_geojson"] == (date(2023, 6, 7), None, 20_000)
    assert c.get("/geo/hotspots", params={"date": "2023-06-07", "limit": 0}).status_code == 422


def test_unknown_fire_history_is_404(client):
    c, _ = client
    assert c.get("/fires/nope/history").status_code == 404

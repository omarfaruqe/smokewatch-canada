"""API wiring and validation tests; queries are replaced with fakes (no database)."""

from datetime import date

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from smokewatch.api import main, queries  # noqa: E402


class _FakeEngine:
    """Stands in for the SQLAlchemy engine where code opens its own connection."""

    def connect(self):
        return self

    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


@pytest.fixture
def client(monkeypatch):
    main.app.dependency_overrides[main.get_conn] = lambda: None
    main.shapes_cache.plain = main.shapes_cache.gzipped = None
    monkeypatch.setattr(main, "get_engine", _FakeEngine)
    calls = {}

    def fake(name, result):
        def _f(conn, *args):
            calls[name] = args
            return result
        monkeypatch.setattr(queries, name, _f)

    fake("national_daily", [{"day": "2023-06-07", "population_exposed_high_risk": 1}])
    fake("division_exposure", [{"cduid": "2466"}])
    fake("hotspots_geojson", '{"type": "FeatureCollection", "features": []}')
    fake("division_shapes_geojson", '{"type": "FeatureCollection", "features": []}')
    fake("first_nations_geojson", '{"type": "FeatureCollection", "features": []}')
    fake("fire_history", [])
    fake("forecast_skill", [{"lead_bucket": "00-06h", "mae": 0.2}])
    fake("pipeline_health", [{"dataset": "hotspots", "data_through": "2026-06-07T20:00:00Z"}])
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


def test_dashboard_is_served(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200 and "SmokeWatch" in r.text and "maplibre" in r.text


def test_pipeline_health_endpoint(client):
    c, calls = client
    r = c.get("/health/pipeline")
    assert r.status_code == 200 and r.json()[0]["dataset"] == "hotspots"
    assert calls["pipeline_health"] == ()


def test_cache_headers(client):
    c, _ = client
    data = c.get("/exposure", params={"date": "2023-06-07"})
    assert data.headers["cache-control"].startswith("public, max-age=")
    assert c.get("/health/pipeline").headers["cache-control"] == "no-store"
    assert "cache-control" not in c.get("/exposure", params={"date": "bad"}).headers


def test_forecast_skill_endpoint(client):
    c, calls = client
    r = c.get("/aqhi/forecast-skill")
    assert r.status_code == 200 and r.json()[0]["lead_bucket"] == "00-06h"
    assert calls["forecast_skill"] == ()


def test_numeric_values_are_json_numbers():
    from decimal import Decimal

    from smokewatch.api.queries import _plain

    assert _plain(Decimal("0.20")) == 0.2 and isinstance(_plain(Decimal("1")), float)
    assert _plain(5) == 5 and _plain("x") == "x" and _plain(None) is None


def test_geojson_is_passed_through_with_type_and_shape_cache(client):
    c, _ = client
    r = c.get("/geo/hotspots", params={"date": "2023-06-07"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/geo+json")
    assert r.json() == {"type": "FeatureCollection", "features": []}
    shapes = c.get("/geo/census-divisions/shapes")
    assert shapes.headers["cache-control"] == "public, max-age=86400"


def test_large_responses_are_gzipped(client, monkeypatch):
    c, _ = client
    big = '{"type": "FeatureCollection", "features": [' + ",".join(['{"a": 1}'] * 500) + "]}"
    monkeypatch.setattr(queries, "hotspots_geojson", lambda conn, *a: big)
    r = c.get("/geo/hotspots", params={"date": "2023-06-07"}, headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip" and len(r.json()["features"]) == 500


def test_shapes_are_built_once_and_served_gzipped(client, monkeypatch):
    c, _ = client
    builds = []
    big = '{"type": "FeatureCollection", "features": [' + ",".join(['{"a": 1}'] * 500) + "]}"
    monkeypatch.setattr(queries, "division_shapes_geojson", lambda conn: builds.append(1) or big)
    main.shapes_cache.plain = main.shapes_cache.gzipped = None
    for _ in range(3):
        r = c.get("/geo/census-divisions/shapes", headers={"Accept-Encoding": "gzip"})
        assert r.headers["content-encoding"] == "gzip" and len(r.json()["features"]) == 500
    plain = c.get("/geo/census-divisions/shapes", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers and len(plain.json()["features"]) == 500
    assert len(builds) == 1


def test_first_nations_endpoint_passes_date_and_province(client):
    c, calls = client
    r = c.get("/geo/first-nations", params={"date": "2023-06-07", "province": "QC"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/geo+json")
    assert calls["first_nations_geojson"] == (date(2023, 6, 7), "QC")
    assert c.get("/geo/first-nations", params={"date": "2023-06-07", "province": "XX"}
                 ).status_code == 422

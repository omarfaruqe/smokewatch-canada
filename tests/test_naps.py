"""Offline tests for the NAPS extractor and parsers (fixtures mirror the real file layout)."""

import json

import pytest

from smokewatch.extractors import naps
from smokewatch.storage import LocalStore

HOURLY = (
    "﻿File generated on // Fichier créé sur, 2026-06-19\n\n"
    "Pollutant // Polluant:, PM2.5\nUnits // Unités, µg/m3\n"
    "Note // Note,Data is hour ending local standard time // Données en heure normale locale\n"
    "Note // Note,Zeros are valid. -999 denotes no data available // ...\n\n"
    "Pollutant//Polluant,Method Code//Code Méthode,NAPS ID//Identifiant SNPA,City//Ville,"
    "Province/Territory//Province/Territoire,Latitude//Latitude,Longitude//Longitude,Date//Date,"
    + ",".join(f"H{h:02d}//H{h:02d}" for h in range(1, 25)) + "\n"
    "PM2.5,184,050103,Montréal,QC,45.64103,-73.49968,2023-01-01,"
    + ",".join(["4"] * 11 + ["-999"] + ["0"] * 12) + "\n"
).encode("utf-8")

STATIONS = (
    '"*Stations2024",""\n"*Definitions_Définitions",""\n"*DataSources_SourcesdesDonnées",""\n'
    '"**********Stations2024**********",""\n'
    '"NAPS_ID","Station_Name","Timezone_UTC","CD"\n'
    '"Identifiant_SNPA","Nom_de_la_station","Fuseau_horaire_TUC","DR"\n'
    '"050103","Montréal-Est","-5","2466"\n'
    '"010102","St. John\'s","-3.5","1001"\n'
    '"**********Definitions_Définitions**********",""\n"x","y"\n'
).encode("utf-8")


def test_urls_match_portal_encoding():
    assert naps.file_url("air/x/y.csv").endswith("/file?path=/air%2Fx%2Fy.csv")
    assert "path_contents?path=/air%2Fmonitor%2F" in naps.listing_url(2023)
    assert "%2F2023%2FContinuousData-DonneesContinu%2F" in naps.listing_url(2023)


def test_parse_hourly_skips_preamble_and_keeps_text():
    pytest.importorskip("pandas")
    from smokewatch.loaders.naps import parse_hourly

    df = parse_hourly(HOURLY)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["naps_id"] == "050103" and row["date"] == "2023-01-01"  # leading zero kept
    assert row["h12"] == "-999" and row["h24"] == "0"


def test_parse_stations_reads_first_block_only():
    pytest.importorskip("pandas")
    from smokewatch.loaders.naps import parse_stations

    st = parse_stations(STATIONS)
    assert list(st.columns) == ["naps_id", "station_name", "timezone_utc", "cd"]
    assert st["timezone_utc"].tolist() == ["-5", "-3.5"]


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self._p, self.content = payload, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class FakePortal:
    def __init__(self, last_modified="2026-06-24"):
        self.lm, self.headers, self.urls = last_modified, {}, []

    def get(self, url, params=None, timeout=None):
        self.urls.append(url)
        if "path_contents" in url:
            return FakeResponse({"path_contents": [
                {"name": "PM25_2023.csv", "is_directory": False, "last_modified": self.lm,
                 "path": "air/x/PM25_2023.csv"}]})
        return FakeResponse(content=HOURLY)


def test_fetch_year_skips_unless_source_updated(tmp_path):
    store = LocalStore(tmp_path)
    [r] = naps.fetch_year(store, 2023, ("PM25",), session=FakePortal())
    assert not r.skipped and r.key == "naps/hourly/PM25/year=2023/PM25_2023.csv"
    m = json.loads(store.get("naps/hourly/PM25/year=2023/_manifest.json"))
    assert m["source_last_modified"] == "2026-06-24"

    s = FakePortal()
    [r] = naps.fetch_year(store, 2023, ("PM25",), session=s)
    assert r.skipped and len(s.urls) == 1  # listing only, no download

    [r] = naps.fetch_year(store, 2023, ("PM25",), session=FakePortal("2026-09-01"))
    assert not r.skipped


def test_fetch_year_rejects_unpublished_pollutant(tmp_path):
    with pytest.raises(ValueError, match="CO_2023.csv not published"):
        naps.fetch_year(LocalStore(tmp_path), 2023, ("CO",), session=FakePortal())

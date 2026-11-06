"""Offline tests for the CWFIS archive downloader."""

import json

import pytest

from smokewatch.extractors import cwfis_archive
from smokewatch.storage import LocalStore


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, content=b"PK\x03\x04fake"):
        self.content, self.headers, self.urls = content, {}, []

    def get(self, url, timeout=None):
        self.urls.append(url)
        return FakeResponse(self.content)


def test_downloads_once_then_skips(tmp_path):
    store = LocalStore(tmp_path)
    s = FakeSession()
    key, size, skipped = cwfis_archive.fetch_season_perimeters(store, 2023, session=s)
    assert key == "cwfis/perimeters_archive/year=2023/2023_perimeters.zip" and not skipped
    assert s.urls == [f"{cwfis_archive.ARCHIVE_URL}/2023_perimeters.zip"]
    manifest = json.loads(store.get("cwfis/perimeters_archive/year=2023/_manifest.json"))
    assert manifest["year"] == 2023
    _, _, skipped = cwfis_archive.fetch_season_perimeters(store, 2023, session=s)
    assert skipped and len(s.urls) == 1


def test_rejects_non_zip(tmp_path):
    with pytest.raises(RuntimeError, match="did not return a zip"):
        cwfis_archive.fetch_season_perimeters(
            LocalStore(tmp_path), 2023, session=FakeSession(b"<html>not found</html>"))

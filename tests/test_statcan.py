"""Offline tests for the StatCan reference-file downloader (no network)."""

import json

from smokewatch.extractors import statcan
from smokewatch.storage import LocalStore


class FakeStream:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.data


class FakeSession:
    def __init__(self, body=None):
        self.headers, self.urls, self.body = {}, [], body

    def get(self, url, stream=False, timeout=None):
        self.urls.append(url)
        return FakeStream(self.body or (b"PK-fake-" + url.encode()))


def test_fetch_writes_file_and_manifest(tmp_path):
    store = LocalStore(tmp_path)
    s = FakeSession()
    [r] = statcan.fetch(store, ["census_divisions"], session=s)
    assert s.urls == [statcan.FILES["census_divisions"][0]]
    assert store.get(r.key).startswith(b"PK-fake-")
    m = json.loads(store.get("statcan/census2021/boundaries/lcd_000b21a_e_manifest.json"))
    assert m["sha256"] == r.sha256 and m["bytes"] == r.bytes


def test_fetch_skips_existing_unless_forced(tmp_path):
    store = LocalStore(tmp_path)
    statcan.fetch(store, ["provinces"], session=FakeSession())
    s = FakeSession()
    [r] = statcan.fetch(store, ["provinces"], session=s)
    assert r.skipped and s.urls == []
    [r] = statcan.fetch(store, ["provinces"], force=True, session=s)
    assert not r.skipped and len(s.urls) == 1


def test_fetch_rejects_html_instead_of_zip(tmp_path):
    import pytest

    store = LocalStore(tmp_path)
    with pytest.raises(RuntimeError, match="did not return a zip"):
        statcan.fetch(store, ["geo_attributes"], session=FakeSession(b"<!DOCTYPE html>"))
    assert not store.exists("statcan/census2021/attributes/2021_92-151_X_manifest.json")

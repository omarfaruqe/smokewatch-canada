"""Download CWFIS yearly archive files (season fire perimeters) into bronze.

    cwfis/perimeters_archive/year=YYYY/{YYYY_perimeters.zip,_manifest.json}

The archive holds the final perimeters of each season. Daily growth for past seasons is not
available, so these complement (not replace) the SCD2 history built from daily snapshots.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import requests

from smokewatch.extractors.common import new_session
from smokewatch.storage import BronzeStore, put_json

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://cwfis.cfs.nrcan.gc.ca/downloads/hotspots/archive"


def folder_for(year: int) -> str:
    return f"cwfis/perimeters_archive/year={year}"


def fetch_season_perimeters(
    store: BronzeStore, year: int, force: bool = False, session: requests.Session | None = None
) -> tuple[str, int, bool]:
    folder = folder_for(year)
    name = f"{year}_perimeters.zip"
    if not force and store.exists(f"{folder}/_manifest.json"):
        log.info("skip %s (already in bronze)", name)
        return f"{folder}/{name}", 0, True
    session = session or new_session()
    url = f"{ARCHIVE_URL}/{name}"
    resp = session.get(url, timeout=600)
    resp.raise_for_status()
    data = resp.content
    if data[:2] != b"PK":
        raise RuntimeError(f"{url} did not return a zip archive")
    store.put(f"{folder}/{name}", data, content_type="application/zip")
    put_json(store, f"{folder}/_manifest.json", {
        "source": "CWFIS (Natural Resources Canada)", "url": url, "year": year,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "licence": "Open Government Licence - Canada",
    })
    log.info("wrote %s (%.1f MB)", name, len(data) / 1e6)
    return f"{folder}/{name}", len(data), False

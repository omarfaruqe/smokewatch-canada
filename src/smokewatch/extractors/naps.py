"""Extract ECCC National Air Pollution Surveillance (NAPS) archive data into bronze.

NAPS publishes one CSV per pollutant per year of continuous hourly data (station-day rows,
H01..H24 in local standard time) and a station list. These are the historical record behind
AQHI, so PM2.5, O3 and NO2 let us compute AQHI for past seasons.

    naps/hourly/<POLLUTANT>/year=YYYY/{<POLLUTANT>_YYYY.csv,_manifest.json}
    naps/stations/{StationsNAPS-StationsSNPA.csv,_manifest.json}

Yearly files are re-downloaded only when the portal reports a newer last_modified date.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from smokewatch.config import settings
from smokewatch.extractors.common import get_json, new_session
from smokewatch.storage import BronzeStore, put_json

log = logging.getLogger(__name__)

BASE = "air/monitor/national-air-pollution-surveillance-naps-program"
STATIONS_PATH = f"{BASE}/ProgramInformation-InformationProgramme/StationsNAPS-StationsSNPA.csv"
DEFAULT_POLLUTANTS = ("PM25", "O3", "NO2")


def _encode(path: str) -> str:
    """Portal paths are passed as path=/<segments joined by %2F>."""
    return "/" + quote(path.strip("/"), safe="")


def listing_url(year: int) -> str:
    folder = f"{BASE}/Data-Donnees/{year}/ContinuousData-DonneesContinu/HourlyData-DonneesHoraires/"
    return f"{settings.naps_api_url}/path_contents?path={_encode(folder)}"


def file_url(path: str) -> str:
    return f"{settings.naps_api_url}/file?path={_encode(path)}"


@dataclass
class NapsResult:
    name: str
    key: str
    bytes: int
    skipped: bool


def _download(session: requests.Session, url: str) -> bytes:
    resp = session.get(url, timeout=300)
    resp.raise_for_status()
    if not resp.content:
        raise RuntimeError(f"empty response from {url}")
    return resp.content


def _write(store: BronzeStore, folder: str, name: str, data: bytes, extra: dict) -> str:
    key = f"{folder}/{name}"
    store.put(key, data, content_type="text/csv")
    put_json(store, f"{folder}/_manifest.json", {
        "source": "ECCC National Air Pollution Surveillance (NAPS)",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "licence": "Open Government Licence - Canada", **extra,
    })
    return key


def fetch_year(
    store: BronzeStore, year: int, pollutants: tuple[str, ...] = DEFAULT_POLLUTANTS,
    force: bool = False, session: requests.Session | None = None,
) -> list[NapsResult]:
    import json

    session = session or new_session()
    files = {f["name"]: f for f in get_json(session, listing_url(year))["path_contents"]
             if not f.get("is_directory")}
    results = []
    for pol in pollutants:
        name = f"{pol}_{year}.csv"
        if name not in files:
            raise ValueError(f"{name} not published for {year}; available: {sorted(files)}")
        meta = files[name]
        folder = f"naps/hourly/{pol}/year={year}"
        manifest_key = f"{folder}/_manifest.json"
        if not force and store.exists(manifest_key):
            prev = json.loads(store.get(manifest_key))
            if prev.get("source_last_modified") == meta.get("last_modified"):
                log.info("skip %s (unchanged since %s)", name, meta.get("last_modified"))
                results.append(NapsResult(name, f"{folder}/{name}", 0, True))
                continue
        data = _download(session, file_url(meta["path"]))
        key = _write(store, folder, name, data, {
            "url": file_url(meta["path"]), "pollutant": pol, "year": year,
            "source_last_modified": meta.get("last_modified"),
        })
        log.info("wrote %s (%.1f MB) to %s", name, len(data) / 1e6, key)
        results.append(NapsResult(name, key, len(data), False))
    return results


def fetch_stations(store: BronzeStore, session: requests.Session | None = None) -> NapsResult:
    session = session or new_session()
    data = _download(session, file_url(STATIONS_PATH))
    name = STATIONS_PATH.rsplit("/", 1)[-1]
    key = _write(store, "naps/stations", name, data, {"url": file_url(STATIONS_PATH)})
    return NapsResult(name, key, len(data), False)

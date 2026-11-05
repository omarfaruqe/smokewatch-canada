"""Download Statistics Canada 2021 Census reference files into bronze.

These are static reference datasets, so each file is stored once (no date partition) with
a manifest; re-runs skip files already present unless forced.

    statcan/census2021/boundaries/<name>.zip   cartographic boundary files (Shapefile)
    statcan/census2021/tables/<pid>-eng.zip    data tables (CSV)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from smokewatch.extractors.common import MAX_RETRIES, new_session
from smokewatch.storage import BronzeStore, put_json

log = logging.getLogger(__name__)

BOUNDARY_BASE = (
    "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/"
    "files-fichiers"
)
TABLE_BASE = "https://www150.statcan.gc.ca/n1/tbl/csv"

# name -> (url, bronze key, description)
FILES: dict[str, tuple[str, str, str]] = {
    "census_divisions": (
        f"{BOUNDARY_BASE}/lcd_000b21a_e.zip",
        "statcan/census2021/boundaries/lcd_000b21a_e.zip",
        "Census divisions, cartographic boundary file, 2021, Shapefile, EPSG:3347",
    ),
    "provinces": (
        f"{BOUNDARY_BASE}/lpr_000b21a_e.zip",
        "statcan/census2021/boundaries/lpr_000b21a_e.zip",
        "Provinces and territories, cartographic boundary file, 2021, Shapefile, EPSG:3347",
    ),
    "population_cd": (
        f"{TABLE_BASE}/98100007-eng.zip",
        "statcan/census2021/tables/98100007-eng.zip",
        "Table 98-10-0007-01 Population and dwelling counts: Canada and census divisions",
    ),
}


@dataclass
class DownloadResult:
    name: str
    key: str
    bytes: int
    sha256: str
    skipped: bool


def _download(session: requests.Session, url: str) -> bytes:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with session.get(url, stream=True, timeout=300) as resp:
                resp.raise_for_status()
                return b"".join(resp.iter_content(chunk_size=1 << 20))
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            log.warning("download failed (%s), retry %d", exc, attempt)
    raise RuntimeError("unreachable")


def fetch(
    store: BronzeStore,
    names: list[str] | None = None,
    force: bool = False,
    session: requests.Session | None = None,
) -> list[DownloadResult]:
    session = session or new_session()
    results = []
    for name in names or list(FILES):
        url, key, desc = FILES[name]
        manifest_key = key.rsplit(".", 1)[0] + "_manifest.json"
        if not force and store.exists(manifest_key):
            log.info("skip %s (already in bronze)", name)
            results.append(DownloadResult(name, key, 0, "", True))
            continue
        data = _download(session, url)
        digest = hashlib.sha256(data).hexdigest()
        store.put(key, data, content_type="application/zip")
        put_json(store, manifest_key, {
            "source": "Statistics Canada", "url": url, "description": desc,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(data), "sha256": digest,
            "licence": "Statistics Canada Open Licence",
        })
        log.info("wrote %s (%.1f MB) to %s", name, len(data) / 1e6, key)
        results.append(DownloadResult(name, key, len(data), digest, False))
    return results

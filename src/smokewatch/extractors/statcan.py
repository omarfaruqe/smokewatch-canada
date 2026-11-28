"""Download Statistics Canada 2021 Census reference files into bronze.

These are static reference datasets, so each file is stored once (no date partition) with
a manifest; re-runs skip files already present unless forced.

    statcan/census2021/boundaries/<name>.zip   cartographic boundary files (Shapefile)
    statcan/census2021/tables/<pid>-eng.zip    data tables (CSV)
    statcan/census2021/profile/da_age_indigenous.csv   Census Profile, dissemination areas
    isc/first_nations/Premiere_Nation_First_Nation_CSV.zip   ISC First Nation locations

The Census Profile comes from StatCan's SDMX web data service (the comprehensive download
page sits behind a browser challenge, which we do not try to get around).
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
ATTRIBUTE_BASE = (
    "https://www12.statcan.gc.ca/census-recensement/2021/geo/aip-pia/attribute-attribs/"
    "files-fichiers"
)

PROFILE_SDMX = "https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest"

# Census Profile characteristic codes (codelist CL_CHARACTERISTIC of dataflow DF_DA).
PROFILE_CHARACTERISTICS = {
    "1": "population_2021",
    "10": "age_0_4",
    "24": "age_65_plus",
    "1389": "indigenous_identity",
}
ISC_FIRST_NATIONS = (
    "https://data.sac-isc.gc.ca/geomatics/rest/directories/arcgisoutput/"
    "DonneesOuvertes_OpenData/Premiere_Nation_First_Nation/Premiere_Nation_First_Nation_CSV.zip"
)

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
    "geo_attributes": (
        f"{ATTRIBUTE_BASE}/2021_92-151_X.zip",
        "statcan/census2021/attributes/2021_92-151_X.zip",
        "Geographic Attribute File 92-151-X: dissemination blocks with 2021 population and "
        "dissemination area representative points",
    ),
    "population_cd": (
        f"{TABLE_BASE}/98100007-eng.zip",
        "statcan/census2021/tables/98100007-eng.zip",
        "Table 98-10-0007-01 Population and dwelling counts: Canada and census divisions",
    ),
    "profile_da": (
        f"{PROFILE_SDMX}/data/STC_CP,DF_DA/A5..1.{'+'.join(PROFILE_CHARACTERISTICS)}.1"
        "?format=csv",
        "statcan/census2021/profile/da_age_indigenous.csv",
        "2021 Census Profile (SDMX DF_DA), dissemination areas, total gender, counts: "
        "population, 0 to 4 years, 65 years and over, Indigenous identity (25% sample)",
    ),
    "first_nations": (
        ISC_FIRST_NATIONS,
        "isc/first_nations/Premiere_Nation_First_Nation_CSV.zip",
        "Indigenous Services Canada, First Nation locations (band office points, NAD83 CSRS)",
    ),
}

# Publisher and licence where they differ from Statistics Canada.
PUBLISHERS = {
    "first_nations": ("Indigenous Services Canada", "Open Government Licence - Canada"),
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
            with session.get(url, stream=True, timeout=600) as resp:
                resp.raise_for_status()
                return b"".join(resp.iter_content(chunk_size=1 << 20))
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            log.warning("download failed (%s), retry %d", exc, attempt)
    raise RuntimeError("unreachable")


def check_payload(key: str, url: str, data: bytes) -> None:
    """Reject HTML error or challenge pages saved in place of the real file."""
    if key.endswith(".zip") and data[:2] != b"PK":
        raise RuntimeError(f"{url} did not return a zip archive (got {data[:60]!r})")
    if key.endswith(".csv") and not data.removeprefix(b"\xef\xbb\xbf").startswith(b"DATAFLOW,"):
        raise RuntimeError(f"{url} did not return SDMX CSV (got {data[:60]!r})")


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
        check_payload(key, url, data)
        digest = hashlib.sha256(data).hexdigest()
        content_type = "text/csv" if key.endswith(".csv") else "application/zip"
        store.put(key, data, content_type=content_type)
        publisher, licence = PUBLISHERS.get(
            name, ("Statistics Canada", "Statistics Canada Open Licence"))
        put_json(store, manifest_key, {
            "source": publisher, "url": url, "description": desc,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(data), "sha256": digest,
            "licence": licence,
        })
        log.info("wrote %s (%.1f MB) to %s", name, len(data) / 1e6, key)
        results.append(DownloadResult(name, key, len(data), digest, False))
    return results

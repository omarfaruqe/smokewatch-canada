"""Client for ECCC MSC GeoMet OGC API - Features (https://api.weather.gc.ca).

Pages by following the `next` link that pygeoapi returns, so it does not depend on
server-side page-size caps.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import requests

from smokewatch.config import settings
from smokewatch.extractors.common import get_json, new_session

log = logging.getLogger(__name__)

PAGE_SIZE = 5_000
MAX_PAGES = 1_000  # safety stop


def day_interval(day: date) -> str:
    """OGC datetime interval covering one UTC day (closed interval, so end at :59:59)."""
    return f"{day.isoformat()}T00:00:00Z/{day.isoformat()}T23:59:59Z"


def items_url(collection: str) -> str:
    return f"{settings.eccc_api_url.rstrip('/')}/collections/{collection}/items"


def fetch_items(
    collection: str,
    params: dict | None = None,
    session: requests.Session | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict]:
    session = session or new_session()
    query = {"f": "json", "limit": page_size, **(params or {})}
    url: str | None = items_url(collection)
    features: list[dict] = []
    for page_no in range(MAX_PAGES):
        page = get_json(session, url, query if page_no == 0 else None)
        batch = page.get("features", [])
        features.extend(batch)
        log.info("%s page %d: %d features", collection, page_no + 1, len(batch))
        nxt = next((ln["href"] for ln in page.get("links", []) if ln.get("rel") == "next"), None)
        if not batch or not nxt:
            return features
        url = nxt
    raise RuntimeError(f"{collection}: exceeded {MAX_PAGES} pages")


def next_day(day: date) -> date:
    return day + timedelta(days=1)

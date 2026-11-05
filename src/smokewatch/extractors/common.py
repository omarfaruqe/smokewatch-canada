"""Shared helpers for extractors: HTTP retries and bronze partition writes."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from smokewatch.config import settings
from smokewatch.storage import BronzeStore, put_json

log = logging.getLogger(__name__)

MAX_RETRIES = 4


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = settings.user_agent
    return s


def get_json(session: requests.Session, url: str, params: dict | None = None) -> dict:
    """GET a JSON document with exponential-backoff retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == MAX_RETRIES:
                raise
            wait = 2**attempt
            log.warning("request failed (%s), retry %d in %ds", exc, attempt, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


@dataclass
class PartitionResult:
    prefix: str
    feature_count: int
    data_key: str
    manifest_key: str
    sha256: str


def write_feature_partition(
    store: BronzeStore, prefix: str, features: list[dict], manifest_extra: dict
) -> PartitionResult:
    """Write <prefix>/items.geojson + <prefix>/_manifest.json (overwrite = idempotent)."""
    payload = json.dumps(
        {"type": "FeatureCollection", "features": features}, ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    data_key = f"{prefix}/items.geojson"
    manifest_key = f"{prefix}/_manifest.json"
    store.put(data_key, payload, content_type="application/geo+json")
    put_json(
        store,
        manifest_key,
        {
            **manifest_extra,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "feature_count": len(features),
            "sha256": digest,
            "licence": "Open Government Licence - Canada",
        },
    )
    log.info("wrote %d features to %s", len(features), data_key)
    return PartitionResult(prefix, len(features), data_key, manifest_key, digest)

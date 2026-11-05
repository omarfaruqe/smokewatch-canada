"""Settings loaded from environment variables (and .env if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    minio_user: str = os.getenv("MINIO_ROOT_USER", "smokewatch")
    minio_password: str = os.getenv("MINIO_ROOT_PASSWORD", "")
    bronze_bucket: str = os.getenv("BRONZE_BUCKET", "bronze")
    cwfis_wfs_url: str = os.getenv(
        "CWFIS_WFS_URL", "https://cwfis.cfs.nrcan.gc.ca/geoserver/public/ows"
    )
    user_agent: str = os.getenv("HTTP_USER_AGENT", "smokewatch-canada/0.1")


settings = Settings()

"""Settings loaded from environment variables (and .env if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    s3_endpoint: str = os.getenv("S3_ENDPOINT", "http://localhost:8333")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "smokewatch")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "")
    bronze_bucket: str = os.getenv("BRONZE_BUCKET", "bronze")
    cwfis_wfs_url: str = os.getenv(
        "CWFIS_WFS_URL", "https://cwfis.cfs.nrcan.gc.ca/geoserver/public/ows"
    )
    eccc_api_url: str = os.getenv("ECCC_API_URL", "https://api.weather.gc.ca")
    user_agent: str = os.getenv("HTTP_USER_AGENT", "smokewatch-canada/0.1")


settings = Settings()

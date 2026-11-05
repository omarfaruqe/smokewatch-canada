"""Bronze-layer storage: one interface, two backends (local disk for tests/dev, MinIO/S3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from smokewatch.config import settings


class BronzeStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...
    def exists(self, key: str) -> bool: ...
    def get(self, key: str) -> bytes: ...


class LocalStore:
    """Writes objects under a root folder, mirroring the S3 key layout."""

    def __init__(self, root: str | Path = "data/bronze") -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)  # atomic overwrite -> re-runs are idempotent
        return str(path)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class S3Store:
    """MinIO (or any S3-compatible) bucket."""

    def __init__(self, bucket: str | None = None) -> None:
        import boto3

        self.bucket = bucket or settings.bronze_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_user,
            aws_secret_access_key=settings.minio_password,
            region_name="us-east-1",
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{key}"

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()


def get_store(sink: str) -> BronzeStore:
    if sink == "local":
        return LocalStore()
    if sink == "s3":
        return S3Store()
    raise ValueError(f"unknown sink: {sink!r} (use 'local' or 's3')")


def put_json(store: BronzeStore, key: str, obj: dict) -> str:
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return store.put(key, data, content_type="application/json")

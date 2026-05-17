from __future__ import annotations
from io import BytesIO

from minio import Minio

from .config import settings


def client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def get_bytes(key: str) -> bytes:
    c = client()
    r = c.get_object(settings.minio_bucket, key)
    try:
        return r.read()
    finally:
        r.close()
        r.release_conn()


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    c = client()
    c.put_object(
        settings.minio_bucket, key, BytesIO(data), length=len(data), content_type=content_type
    )

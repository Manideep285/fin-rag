from __future__ import annotations
from io import BytesIO
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from .config import settings


def _client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> None:
    c = _client()
    if not c.bucket_exists(settings.minio_bucket):
        c.make_bucket(settings.minio_bucket)


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    c = _client()
    c.put_object(
        settings.minio_bucket,
        key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def get_object(key: str) -> bytes:
    c = _client()
    resp = c.get_object(settings.minio_bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def storage_key(project_id, source_id, filename: str) -> str:
    return f"{project_id}/{source_id}/{filename}"

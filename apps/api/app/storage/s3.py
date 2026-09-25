import logging
from typing import Any, Protocol
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

log = logging.getLogger(__name__)


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def presigned_get(self, key: str, filename: str, expires_in: int) -> str: ...


def _content_disposition(filename: str) -> str:
    # ASCII fallback + RFC 5987 UTF-8 form; the original name is display-only, never a path.
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "") or "resume"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _client(endpoint: str | None) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        # Path-style works for MinIO and real S3 alike; sigv4 is required for presigned GETs.
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


class S3Storage:
    """S3-compatible storage: MinIO locally, real S3 by pointing S3_ENDPOINT elsewhere (or unsetting it)."""

    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self._client = _client(settings.s3_endpoint)
        # Presigning is offline (no network), so it can use the browser-facing host.
        self._presign_client = _client(settings.s3_public_endpoint or settings.s3_endpoint)

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            log.info("Creating private bucket %s", self.bucket)
            self._client.create_bucket(Bucket=self.bucket)  # no public-read policy, ever

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await run_in_threadpool(
            self._client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )

    async def get(self, key: str) -> bytes:
        obj = await run_in_threadpool(self._client.get_object, Bucket=self.bucket, Key=key)
        body: bytes = await run_in_threadpool(obj["Body"].read)
        return body

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self._client.delete_object, Bucket=self.bucket, Key=key)

    async def presigned_get(self, key: str, filename: str, expires_in: int) -> str:
        url: str = self._presign_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": _content_disposition(filename),
            },
            ExpiresIn=expires_in,
        )
        return url


_storage: S3Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage()
    return _storage

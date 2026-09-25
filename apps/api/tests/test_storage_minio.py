"""Round-trip against the real MinIO from docker-compose: upload → presigned GET → same bytes.
Skipped when MinIO isn't reachable."""

from uuid import uuid4

import httpx
import pytest

from app.core.config import settings
from app.storage.s3 import S3Storage
from tests.conftest import PDF_BYTES


def _minio_up() -> bool:
    if not settings.s3_endpoint:
        return False
    try:
        return httpx.get(f"{settings.s3_endpoint}/minio/health/live", timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _minio_up(), reason="MinIO not reachable")


async def test_upload_then_presigned_download() -> None:
    storage = S3Storage()
    storage.ensure_bucket()
    key = f"leads/test-{uuid4()}/resume-{uuid4()}.pdf"
    await storage.put(key, PDF_BYTES, "application/pdf")
    try:
        url = await storage.presigned_get(key, "Ada Lovelace – CV.pdf", 60)
        async with httpx.AsyncClient() as http:
            res = await http.get(url)
            assert res.status_code == 200
            assert res.content == PDF_BYTES
            assert "attachment" in res.headers["content-disposition"]

            # The bucket is private: the bare object URL is refused.
            bare = await http.get(f"{settings.s3_endpoint}/{settings.s3_bucket}/{key}")
            assert bare.status_code == 403
    finally:
        await storage.delete(key)

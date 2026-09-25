"""Test harness.

Runs against a real Postgres (TEST_DATABASE_URL, default: the compose `alma_test` DB). The
schema is rebuilt from prisma/migrations/*/migration.sql on every run — the same SQL that
`prisma migrate deploy` applies — so tests never need Node. Storage and email are fakes
unless a test opts into the real thing.
"""

import io
import os
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

API_DIR = Path(__file__).resolve().parents[1]
_root_env = dotenv_values(API_DIR.parents[1] / ".env")

# Must happen before `app` is imported: settings and the engine are built at import time.
# DATABASE_URL is *overridden*, never defaulted, so tests can't touch the dev database.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or _root_env.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/alma_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
os.environ["ATTORNEY_EMAILS"] = "attorney@example.com,partner@example.com"
os.environ["EMAIL_RETRY_BASE_SECONDS"] = "0"
os.environ["RATE_LIMIT_LEADS"] = "5 per 15 minutes"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SESSION_COOKIE_NAME"] = "session"
for key in ("S3_ENDPOINT", "S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET"):
    if key not in os.environ and _root_env.get(key):
        os.environ[key] = _root_env[key]  # type: ignore[assignment]

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.emails.sender import get_email_sender  # noqa: E402
from app.main import app  # noqa: E402
from app.storage.s3 import get_storage  # noqa: E402

ORIGIN = "http://localhost:3000"
PASSWORD = "correct horse battery staple"
MIGRATIONS = API_DIR / "prisma" / "migrations"


# ---------------------------------------------------------------- fakes


class InMemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def presigned_get(self, key: str, filename: str, expires_in: int) -> str:
        return f"https://storage.test/{key}?expires={expires_in}"


@dataclass
class SentEmail:
    to: str
    subject: str
    html: str
    text: str
    reply_to: str | None


@dataclass
class FakeSender:
    sent: list[SentEmail] = field(default_factory=list)
    fail_times: int = 0  # fail this many sends (across all recipients) before succeeding

    async def send(self, to: str, subject: str, html: str, text: str, reply_to: str | None = None) -> str:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("smtp down")
        self.sent.append(SentEmail(to, subject, html, text, reply_to))
        return f"<fake-{len(self.sent)}@test>"


# ---------------------------------------------------------------- sample files


PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
DOC_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 1024
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200


def make_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def lead_form(**overrides: str) -> dict[str, str]:
    return {"firstName": "Ada", "lastName": "Lovelace", "email": "ada@example.com"} | overrides


def resume_file(
    name: str = "cv.pdf", data: bytes = PDF_BYTES, mime: str = "application/pdf"
) -> dict[str, tuple[str, bytes, str]]:
    return {"resume": (name, data, mime)}


# ---------------------------------------------------------------- fixtures


async def _rebuild_schema() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        for migration in sorted(MIGRATIONS.glob("*/migration.sql")):
            await conn.execute(migration.read_text())
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def migrated_db() -> AsyncIterator[None]:
    # scripts/db-check.sh sets this after `prisma migrate deploy`, so the drift test inspects
    # the database Prisma itself produced rather than our replay of its SQL.
    if os.environ.get("USE_PRISMA_MIGRATED_DB") != "1":
        await _rebuild_schema()
    yield
    await engine.dispose()


@pytest.fixture
def migrated_engine():  # type: ignore[no-untyped-def]
    return engine


@pytest.fixture(autouse=True)
async def clean_state() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE "EmailLog", "Lead", "User" CASCADE'))
    limiter.reset()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def storage() -> InMemoryStorage:
    fake = InMemoryStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
def sender() -> FakeSender:
    fake = FakeSender()
    app.dependency_overrides[get_email_sender] = lambda: fake
    return fake


@pytest.fixture
async def client(storage: InMemoryStorage, sender: FakeSender) -> AsyncIterator[AsyncClient]:
    # ASGITransport runs background tasks to completion before the call returns, so tests can
    # assert on EmailLog rows right after the POST.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://api.test", headers={"Origin": ORIGIN}
    ) as c:
        yield c


@pytest.fixture
async def attorney() -> User:
    async with SessionLocal() as session, session.begin():
        user = User(email="attorney@example.com", password_hash=hash_password(PASSWORD), name="Attorney")
        session.add(user)
    return user


@pytest.fixture
async def authed(client: AsyncClient, attorney: User) -> AsyncClient:
    res = await client.post("/api/v1/auth/login", json={"email": attorney.email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return client

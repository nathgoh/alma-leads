from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

CommaList = Annotated[list[str], NoDecode]

# alma-leads/.env when running from a checkout; absent (and harmless) inside the container.
_PARENTS = Path(__file__).resolve().parents
_REPO_ENV = _PARENTS[4] / ".env" if len(_PARENTS) > 4 else Path(".env")


class Settings(BaseSettings):
    # Real env vars win; for host-side dev, fall back to the monorepo-root .env.
    model_config = SettingsConfigDict(env_file=(_REPO_ENV, ".env"), extra="ignore")

    # One URL for both tools: Prisma reads it as-is, SQLAlchemy via `sqlalchemy_url`.
    database_url: str = "postgresql://postgres:postgres@localhost:5432/alma"

    # Auth
    jwt_secret: str = Field(min_length=32)  # required: no secret has a default
    jwt_ttl_seconds: int = 8 * 60 * 60
    session_cookie_name: str = "session"
    cookie_secure: bool = False

    # CSRF: exact-match list of origins allowed to send unsafe requests.
    allowed_origins: CommaList = ["http://localhost:3000"]

    # Rate limits (slowapi / `limits` syntax)
    rate_limit_enabled: bool = True
    rate_limit_leads: str = "5 per 15 minutes"
    rate_limit_login: str = "10 per minute"

    # Resume uploads
    max_resume_bytes: int = 5 * 1024 * 1024

    # S3 / MinIO
    s3_endpoint: str | None = "http://localhost:9000"
    # Host the *browser* uses for presigned URLs (the API reaches MinIO as `minio:9000`
    # on the compose network, but the signature must match the host the browser hits).
    s3_public_endpoint: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None  # None → default AWS credential chain (IAM role in prod)
    s3_secret_key: str | None = None
    s3_bucket: str = "resumes"
    s3_create_bucket: bool = True
    presign_ttl_seconds: int = 300

    # Email
    email_provider: Literal["smtp", "resend"] = "smtp"
    email_from: str = "Alma Leads <no-reply@alma.local>"
    email_reply_to: str | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    resend_api_key: str | None = None
    attorney_emails: CommaList = ["attorney@example.com"]
    email_max_attempts: int = 3
    email_retry_base_seconds: float = 1.0  # backoff: 1s, 5s, 25s, ...

    # Links in emails point at the web app.
    web_base_url: str = "http://localhost:3000"

    # Local dev seeding (python -m app.seed). Unset → seeding is skipped.
    seed_password: str | None = None

    @field_validator("allowed_origins", "attorney_emails", mode="before")
    @classmethod
    def _split_commas(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def sqlalchemy_url(self) -> str:
        scheme, sep, rest = self.database_url.partition("://")
        if scheme not in {"postgres", "postgresql"}:
            raise ValueError(f"DATABASE_URL must be a postgresql:// URL, got {scheme}://")
        # Prisma-style query params (e.g. ?schema=public) mean nothing to asyncpg.
        return f"postgresql+asyncpg{sep}{rest.split('?', 1)[0]}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()  # fails fast at import if required env is missing

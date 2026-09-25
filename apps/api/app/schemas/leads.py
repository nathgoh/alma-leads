from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, EmailStr, Field

from app.db.enums import EmailKind, EmailStatus, LeadState
from app.schemas.base import ApiModel

NAME_MAX = 100
EMAIL_MAX = 254


def _strip_nonempty(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be blank")
    return v


def _as_utc(v: datetime) -> datetime:
    # TIMESTAMP(3) columns are naive UTC; say so on the wire ("...Z") so browsers don't guess.
    return v.replace(tzinfo=UTC) if v.tzinfo is None else v


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]

Name = Annotated[str, Field(min_length=1, max_length=NAME_MAX), AfterValidator(_strip_nonempty)]


class LeadCreateForm(ApiModel):
    """Text fields of the public multipart submission (the file is validated separately)."""

    first_name: Name
    last_name: Name
    email: Annotated[EmailStr, Field(max_length=EMAIL_MAX)]
    # Honeypot: invisible to humans. Anything here means a bot filled the form.
    website: str = ""


class LeadCreated(ApiModel):
    id: str
    message: str = "Thanks! Your information has been received."


class LeadSummary(ApiModel):
    id: str
    first_name: str
    last_name: str
    email: str
    state: LeadState
    resume_name: str
    created_at: UtcDatetime
    reached_out_at: UtcDatetime | None


class ReachedOutBy(ApiModel):
    id: str
    name: str
    email: str


class EmailLogOut(ApiModel):
    kind: EmailKind
    recipient: str
    status: EmailStatus
    attempts: int
    error: str | None
    sent_at: UtcDatetime | None


class LeadDetail(LeadSummary):
    resume_size: int
    resume_mime: str
    updated_at: UtcDatetime
    reached_out_user: ReachedOutBy | None = Field(default=None, serialization_alias="reachedOutBy")
    emails: list[EmailLogOut]


class LeadPage(ApiModel):
    items: list[LeadSummary]
    total: int
    page: int
    page_size: int


class LeadUpdate(ApiModel):
    state: Literal[LeadState.REACHED_OUT]


class ResumeDownload(ApiModel):
    url: str
    filename: str
    expires_in: int

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import CurrentAttorney
from app.core.config import settings
from app.core.http import require_json
from app.core.rate_limit import leads_limit, limiter
from app.db.enums import LeadState
from app.db.session import get_session, get_session_factory
from app.emails.sender import EmailSender, get_email_sender
from app.emails.service import send_lead_emails
from app.leads import service
from app.leads.files import ResumeRejected, validate_resume
from app.schemas.leads import (
    EMAIL_MAX,
    NAME_MAX,
    LeadCreated,
    LeadCreateForm,
    LeadDetail,
    LeadPage,
    LeadSummary,
    LeadUpdate,
    ResumeDownload,
)
from app.storage.s3 import Storage, get_storage

Session = Annotated[AsyncSession, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]

public_router = APIRouter(prefix="/leads", tags=["leads (public)"])
internal_router = APIRouter(prefix="/leads", tags=["leads (internal)"])


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")


@public_router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(leads_limit)
async def create_lead(
    request: Request,
    first_name: Annotated[str, Form(alias="firstName", max_length=NAME_MAX)],
    last_name: Annotated[str, Form(alias="lastName", max_length=NAME_MAX)],
    email: Annotated[str, Form(max_length=EMAIL_MAX)],
    resume: Annotated[UploadFile, File(description="PDF, DOC, or DOCX")],
    background: BackgroundTasks,
    session: Session,
    storage: StorageDep,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    website: Annotated[str, Form(description="Honeypot; leave empty")] = "",
) -> LeadCreated:
    """Public lead submission (multipart). Returns only an id — nothing else is echoed back."""
    try:
        form = LeadCreateForm.model_validate(
            {"firstName": first_name, "lastName": last_name, "email": email, "website": website}
        )
    except ValidationError as exc:
        raise RequestValidationError(
            [{**err, "loc": ("body", *err["loc"])} for err in exc.errors(include_url=False)]
        ) from None
    if form.website:
        # Honeypot tripped: look successful to the bot, store and send nothing.
        return LeadCreated(id=str(uuid4()))
    try:
        valid = await validate_resume(resume, settings.max_resume_bytes)
    except ResumeRejected as exc:
        raise HTTPException(
            exc.status_code, [{"loc": ["body", "resume"], "msg": str(exc), "type": "value_error"}]
        ) from exc

    lead = await service.create_lead(session, storage, form, valid)
    # Runs after the response is sent: SMTP latency or an outage never fails the submission.
    background.add_task(send_lead_emails, lead.id, sender, session_factory)
    return LeadCreated(id=lead.id)


@internal_router.get("")
async def list_leads(
    _: CurrentAttorney,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    state: LeadState | None = None,
    sort: Literal["newest", "oldest"] = "newest",
) -> LeadPage:
    leads, total = await service.list_leads(
        session, state=state, page=page, page_size=page_size, newest_first=sort == "newest"
    )
    return LeadPage(
        items=[LeadSummary.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        page_size=page_size,
    )


@internal_router.get("/{lead_id}")
async def get_lead(lead_id: str, _: CurrentAttorney, session: Session) -> LeadDetail:
    try:
        return LeadDetail.model_validate(await service.get_lead(session, lead_id))
    except service.LeadNotFound:
        raise _not_found() from None


@internal_router.get("/{lead_id}/resume")
async def get_resume(
    lead_id: str, _: CurrentAttorney, session: Session, storage: StorageDep
) -> ResumeDownload:
    """Mint a short-lived presigned URL. The store serves the bytes; the API only authorizes."""
    try:
        lead = await service.get_lead(session, lead_id)
    except service.LeadNotFound:
        raise _not_found() from None
    ttl = settings.presign_ttl_seconds
    url = await storage.presigned_get(lead.resume_key, lead.resume_name, ttl)
    return ResumeDownload(url=url, filename=lead.resume_name, expires_in=ttl)


@internal_router.patch("/{lead_id}", dependencies=[Depends(require_json)])
async def update_lead(lead_id: str, body: LeadUpdate, user: CurrentAttorney, session: Session) -> LeadDetail:
    """State transition. 409 (not a silent no-op) if the current state has no edge to the target."""
    try:
        lead = await service.transition(session, lead_id, body.state, user.id)
    except service.LeadNotFound:
        raise _not_found() from None
    except service.InvalidTransition:
        raise HTTPException(status.HTTP_409_CONFLICT, "Lead cannot move to that state") from None
    return LeadDetail.model_validate(lead)

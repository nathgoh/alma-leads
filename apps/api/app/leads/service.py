import logging
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import LeadState
from app.db.models import Lead
from app.leads.files import ValidResume
from app.leads.state_machine import sources_for
from app.schemas.leads import LeadCreateForm
from app.storage.s3 import Storage

log = logging.getLogger(__name__)


class LeadNotFound(Exception):
    pass


class InvalidTransition(Exception):
    pass


async def create_lead(
    session: AsyncSession, storage: Storage, form: LeadCreateForm, resume: ValidResume
) -> Lead:
    lead_id = str(uuid4())
    key = f"leads/{lead_id}/resume-{uuid4()}{resume.extension}"
    await storage.put(key, resume.data, resume.mime)
    try:
        async with session.begin():
            lead = Lead(
                id=lead_id,
                first_name=form.first_name,
                last_name=form.last_name,
                email=str(form.email),
                state=LeadState.PENDING,
                resume_key=key,
                resume_name=resume.filename,
                resume_size=len(resume.data),
                resume_mime=resume.mime,
            )
            session.add(lead)
    except Exception:
        # Nothing references the key, so the object is unreachable; clean up best-effort.
        try:
            await storage.delete(key)
        except Exception:
            log.exception("Failed to delete orphaned resume %s", key)
        raise
    return lead


async def list_leads(
    session: AsyncSession, *, state: LeadState | None, page: int, page_size: int, newest_first: bool
) -> tuple[list[Lead], int]:
    filters = [Lead.state == state] if state else []
    order = Lead.created_at.desc() if newest_first else Lead.created_at.asc()
    async with session.begin():
        total = await session.scalar(select(func.count()).select_from(Lead).where(*filters)) or 0
        rows = await session.scalars(
            select(Lead)
            .where(*filters)
            .order_by(order, Lead.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total


async def get_lead(session: AsyncSession, lead_id: str) -> Lead:
    async with session.begin():
        lead = await session.scalar(
            select(Lead)
            .where(Lead.id == lead_id)
            .options(selectinload(Lead.reached_out_user), selectinload(Lead.emails))
            .execution_options(populate_existing=True)
        )
    if lead is None:
        raise LeadNotFound()
    return lead


async def transition(session: AsyncSession, lead_id: str, target: LeadState, attorney_id: str) -> Lead:
    """Single conditional UPDATE: race-free, so two attorneys clicking at once can't both win."""
    values: dict[str, object] = {"state": target}
    if target == LeadState.REACHED_OUT:
        values |= {"reached_out_at": func.now(), "reached_out_by": attorney_id}
    async with session.begin():
        updated_id = await session.scalar(
            update(Lead)
            .where(Lead.id == lead_id, Lead.state.in_(list(sources_for(target))))
            .values(**values)
            .returning(Lead.id)
        )
        if updated_id is None:
            # Zero rows: lead missing (404) or not in an allowed source state (409).
            exists = await session.scalar(select(Lead.id).where(Lead.id == lead_id))
            raise LeadNotFound() if exists is None else InvalidTransition()
    return await get_lead(session, lead_id)

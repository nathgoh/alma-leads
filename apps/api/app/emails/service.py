"""send_lead_emails(): the whole background-task body.

Moving to a real queue (arq/Celery/SQS) is a transport swap: enqueue `lead_id` and call this
same function from the worker.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.enums import EmailKind, EmailStatus
from app.db.models import EmailLog, Lead
from app.emails.sender import EmailSender
from app.emails.templates import render

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)  # TIMESTAMP(3) columns are naive UTC


def _backoff(attempt: int) -> float:
    """Delay after failed attempt N (1-based): 1s, 5s, 25s, ..."""
    return settings.email_retry_base_seconds * float(5 ** (attempt - 1))


async def _deliver(
    session_factory: async_sessionmaker[AsyncSession], sender: EmailSender, lead: Lead, row_id: str
) -> None:
    async with session_factory() as session:
        async with session.begin():
            row = await session.get_one(EmailLog, row_id)
        rendered = render(row.kind, lead)
        reply_to = settings.email_reply_to if row.kind == EmailKind.PROSPECT_CONFIRMATION else lead.email

        for attempt in range(1, settings.email_max_attempts + 1):
            try:
                provider_id = await sender.send(
                    row.recipient, rendered.subject, rendered.html, rendered.text, reply_to=reply_to
                )
            except Exception as exc:  # noqa: BLE001 — any provider failure is recorded, not raised
                log.warning("Email %s to %s failed (attempt %d): %s", row.kind, row.recipient, attempt, exc)
                async with session.begin():
                    row.attempts = attempt
                    row.status = EmailStatus.FAILED
                    row.error = f"{type(exc).__name__}: {exc}"[:1000]
                    session.add(row)
                if attempt < settings.email_max_attempts:
                    await asyncio.sleep(_backoff(attempt))
                continue
            async with session.begin():
                row.attempts = attempt
                row.status = EmailStatus.SENT
                row.provider_id = provider_id
                row.error = None
                row.sent_at = _utcnow()
                session.add(row)
            return


async def _dispatch(
    lead_id: str, sender: EmailSender, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as session, session.begin():
        lead = await session.get(Lead, lead_id)
        if lead is None:
            log.error("send_lead_emails: lead %s not found", lead_id)
            return
        # Idempotent: rows that already exist (e.g. a retried job) are reused, never duplicated.
        existing = {
            (r.kind, r.recipient): r
            for r in await session.scalars(select(EmailLog).where(EmailLog.lead_id == lead_id))
        }
        wanted = [(EmailKind.PROSPECT_CONFIRMATION, lead.email)] + [
            (EmailKind.ATTORNEY_NOTIFICATION, addr) for addr in dict.fromkeys(settings.attorney_emails)
        ]
        rows: list[EmailLog] = []
        for kind, recipient in wanted:
            row = existing.get((kind, recipient))
            if row is None:
                row = EmailLog(lead_id=lead_id, kind=kind, recipient=recipient, status=EmailStatus.PENDING)
                session.add(row)
            if row.status != EmailStatus.SENT:
                rows.append(row)
        await session.flush()
        row_ids = [r.id for r in rows]

    await asyncio.gather(*(_deliver(session_factory, sender, lead, row_id) for row_id in row_ids))


async def send_lead_emails(
    lead_id: str, sender: EmailSender, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Serialize the whole dispatch per lead.

    The row-existence check alone isn't idempotent under concurrency: two workers (a retried
    BackgroundTask, an at-least-once queue redelivery) can both find no rows and both insert +
    send, duplicating the `EmailLog` rows *and* the emails. A session-level advisory lock keyed
    on the lead id makes concurrent callers run one after another, so the second sees `SENT`
    rows and skips them. Session-level (not xact-scoped) because delivery happens outside the
    row-creation transaction, after it has already committed.
    """
    key = func.hashtextextended(lead_id, 0)
    async with session_factory() as lock_session:
        await lock_session.execute(select(func.pg_advisory_lock(key)))
        try:
            await _dispatch(lead_id, sender, session_factory)
        finally:
            await lock_session.execute(select(func.pg_advisory_unlock(key)))

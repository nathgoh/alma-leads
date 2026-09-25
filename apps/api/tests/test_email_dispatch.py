from httpx import AsyncClient
from sqlalchemy import select

from app.db.enums import EmailStatus
from app.db.models import EmailLog
from app.db.session import SessionLocal
from app.emails.service import send_lead_emails
from tests.conftest import FakeSender, lead_form, resume_file


async def _logs() -> list[EmailLog]:
    async with SessionLocal() as s:
        return list(await s.scalars(select(EmailLog)))


async def test_persistent_failure_is_recorded_not_raised(client: AsyncClient, sender: FakeSender) -> None:
    sender.fail_times = 1000
    res = await client.post("/api/v1/leads", data=lead_form(), files=resume_file())
    assert res.status_code == 201  # the prospect's submission never fails because email did

    logs = await _logs()
    assert len(logs) == 3
    for log in logs:
        assert log.status == EmailStatus.FAILED
        assert log.attempts == 3
        assert log.error == "ConnectionError: smtp down"
        assert log.sent_at is None


async def test_transient_failure_is_retried(client: AsyncClient, sender: FakeSender) -> None:
    sender.fail_times = 1
    await client.post("/api/v1/leads", data=lead_form(), files=resume_file())
    logs = await _logs()
    assert all(log.status == EmailStatus.SENT for log in logs)
    assert sorted(log.attempts for log in logs) == [1, 1, 2]
    assert len(sender.sent) == 3


async def test_rerun_only_resends_unsent_rows(client: AsyncClient, sender: FakeSender) -> None:
    sender.fail_times = 1000
    lead_id = (await client.post("/api/v1/leads", data=lead_form(), files=resume_file())).json()["id"]
    sender.fail_times = 0

    await send_lead_emails(lead_id, sender, SessionLocal)
    await send_lead_emails(lead_id, sender, SessionLocal)  # idempotent: nothing left to send

    logs = await _logs()
    assert len(logs) == 3
    assert all(log.status == EmailStatus.SENT for log in logs)
    assert len(sender.sent) == 3

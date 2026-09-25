from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.db.enums import EmailKind, EmailStatus, LeadState
from app.db.models import EmailLog, Lead
from app.db.session import SessionLocal
from app.main import app
from tests.conftest import (
    DOC_BYTES,
    EXE_BYTES,
    ORIGIN,
    FakeSender,
    InMemoryStorage,
    lead_form,
    resume_file,
)


async def _leads() -> list[Lead]:
    async with SessionLocal() as s:
        return list(await s.scalars(select(Lead)))


async def _email_logs() -> list[EmailLog]:
    async with SessionLocal() as s:
        return list(await s.scalars(select(EmailLog).order_by(EmailLog.recipient)))


async def test_submission_creates_lead_uploads_resume_and_sends_both_emails(
    client: AsyncClient, storage: InMemoryStorage, sender: FakeSender
) -> None:
    res = await client.post("/api/v1/leads", data=lead_form(), files=resume_file())

    assert res.status_code == 201
    body = res.json()
    assert set(body) == {"id", "message"}  # nothing else echoed to an anonymous caller

    [lead] = await _leads()
    assert lead.id == body["id"]
    assert (lead.first_name, lead.last_name, lead.email) == ("Ada", "Lovelace", "ada@example.com")
    assert lead.state == LeadState.PENDING
    assert lead.resume_name == "cv.pdf"
    assert lead.resume_mime == "application/pdf"
    assert lead.resume_key.startswith(f"leads/{lead.id}/resume-") and lead.resume_key.endswith(".pdf")
    assert lead.resume_key in storage.objects

    logs = await _email_logs()
    assert [(log.kind, log.recipient, log.status, log.attempts) for log in logs] == [
        (EmailKind.PROSPECT_CONFIRMATION, "ada@example.com", EmailStatus.SENT, 1),
        (EmailKind.ATTORNEY_NOTIFICATION, "attorney@example.com", EmailStatus.SENT, 1),
        (EmailKind.ATTORNEY_NOTIFICATION, "partner@example.com", EmailStatus.SENT, 1),
    ]
    assert all(log.provider_id and log.sent_at for log in logs)

    by_to = {m.to: m for m in sender.sent}
    assert "received" in by_to["ada@example.com"].subject
    notification = by_to["attorney@example.com"]
    assert notification.subject == "New lead: Ada Lovelace"
    assert f"http://localhost:3000/leads/{lead.id}" in notification.text
    assert "ada@example.com" in notification.html
    assert notification.reply_to == "ada@example.com"


async def test_fields_are_escaped_in_html_email(client: AsyncClient, sender: FakeSender) -> None:
    res = await client.post(
        "/api/v1/leads", data=lead_form(firstName="<script>x</script>"), files=resume_file()
    )
    assert res.status_code == 201
    html = next(m.html for m in sender.sent if m.to == "attorney@example.com")
    assert "<script>" not in html and "&lt;script&gt;" in html


async def test_accepts_doc(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/leads", data=lead_form(), files=resume_file("cv.doc", DOC_BYTES, "application/msword")
    )
    assert res.status_code == 201


async def test_names_are_trimmed(client: AsyncClient) -> None:
    res = await client.post("/api/v1/leads", data=lead_form(firstName="  Ada "), files=resume_file())
    assert res.status_code == 201
    [lead] = await _leads()
    assert lead.first_name == "Ada"


async def test_rejects_bad_email(client: AsyncClient) -> None:
    res = await client.post("/api/v1/leads", data=lead_form(email="not-an-email"), files=resume_file())
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "email"]


async def test_rejects_blank_and_long_names(client: AsyncClient) -> None:
    blank = await client.post("/api/v1/leads", data=lead_form(firstName="   "), files=resume_file())
    long = await client.post("/api/v1/leads", data=lead_form(lastName="x" * 101), files=resume_file())
    assert blank.status_code == 422
    assert long.status_code == 422
    assert await _leads() == []


async def test_rejects_missing_file(client: AsyncClient) -> None:
    res = await client.post("/api/v1/leads", data=lead_form())
    assert res.status_code == 422


async def test_rejects_renamed_executable(client: AsyncClient, storage: InMemoryStorage) -> None:
    res = await client.post("/api/v1/leads", data=lead_form(), files=resume_file("cv.pdf", EXE_BYTES))
    assert res.status_code == 415
    assert res.json()["detail"][0]["loc"] == ["body", "resume"]
    assert storage.objects == {}
    assert await _leads() == []


async def test_rejects_oversized_request_before_parsing(client: AsyncClient) -> None:
    big = b"%PDF-1.4\n" + b"0" * (6 * 1024 * 1024)
    res = await client.post("/api/v1/leads", data=lead_form(), files=resume_file("cv.pdf", big))
    assert res.status_code == 413
    assert await _leads() == []


async def test_honeypot_looks_successful_but_stores_nothing(
    client: AsyncClient, storage: InMemoryStorage, sender: FakeSender
) -> None:
    res = await client.post("/api/v1/leads", data=lead_form(website="http://spam"), files=resume_file())
    assert res.status_code == 201
    assert await _leads() == []
    assert storage.objects == {}
    assert sender.sent == []


async def test_failed_insert_deletes_uploaded_object(
    storage: InMemoryStorage, sender: FakeSender, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    from app.leads import service

    real_create = service.create_lead

    async def create_with_broken_insert(session, storage_, form, resume):  # type: ignore[no-untyped-def]
        form.first_name = None  # violates NOT NULL at insert time, after the upload
        return await real_create(session, storage_, form, resume)

    monkeypatch.setattr(service, "create_lead", create_with_broken_insert)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://api.test", headers={"Origin": ORIGIN}) as c:
        res = await c.post("/api/v1/leads", data=lead_form(), files=resume_file())
    assert res.status_code == 500
    assert storage.objects == {}
    assert await _leads() == []


async def test_rate_limit_per_ip(client: AsyncClient) -> None:
    for _ in range(5):
        assert (await client.post("/api/v1/leads", data=lead_form(), files=resume_file())).status_code == 201
    res = await client.post("/api/v1/leads", data=lead_form(), files=resume_file())
    assert res.status_code == 429


async def test_forwarded_ips_get_separate_rate_limit_buckets(
    storage: InMemoryStorage, sender: FakeSender
) -> None:
    # Same shape as production: uvicorn --proxy-headers trusting only the NextJS hop.
    proxied = ProxyHeadersMiddleware(app, trusted_hosts=["127.0.0.1"])
    transport = ASGITransport(app=proxied, client=("127.0.0.1", 5000))  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://api.test", headers={"Origin": ORIGIN}) as c:

        async def submit(ip: str) -> int:
            res = await c.post(
                "/api/v1/leads", data=lead_form(), files=resume_file(), headers={"X-Forwarded-For": ip}
            )
            return res.status_code

        assert [await submit("203.0.113.1") for _ in range(5)] == [201] * 5
        assert await submit("203.0.113.1") == 429
        assert await submit("203.0.113.2") == 201  # a different client isn't punished


async def test_untrusted_hop_cannot_spoof_forwarded_ip(storage: InMemoryStorage, sender: FakeSender) -> None:
    proxied = ProxyHeadersMiddleware(app, trusted_hosts=["127.0.0.1"])
    transport = ASGITransport(app=proxied, client=("198.51.100.9", 5000))  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://api.test", headers={"Origin": ORIGIN}) as c:
        codes = []
        for i in range(6):
            res = await c.post(
                "/api/v1/leads",
                data=lead_form(),
                files=resume_file(),
                headers={"X-Forwarded-For": f"203.0.113.{i}"},  # rotating fake IPs don't help
            )
            codes.append(res.status_code)
        assert codes == [201] * 5 + [429]

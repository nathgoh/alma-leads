from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

import aiosmtplib
import resend
from starlette.concurrency import run_in_threadpool

from app.core.config import settings


class EmailSender(Protocol):
    async def send(
        self, to: str, subject: str, html: str, text: str, reply_to: str | None = None
    ) -> str:  # returns provider message id
        ...


class SMTPSender:
    """Local default: Mailpit on :1025, zero credentials, inbox at :8025."""

    async def send(self, to: str, subject: str, html: str, text: str, reply_to: str | None = None) -> str:
        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        message_id = make_msgid(domain="alma.local")
        msg["Message-ID"] = message_id
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=settings.smtp_starttls,
            timeout=15,
        )
        return message_id


class ResendSender:
    """Production adapter: EMAIL_PROVIDER=resend + RESEND_API_KEY."""

    def __init__(self, api_key: str) -> None:
        resend.api_key = api_key

    async def send(self, to: str, subject: str, html: str, text: str, reply_to: str | None = None) -> str:
        params: resend.Emails.SendParams = {
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }
        if reply_to:
            params["reply_to"] = reply_to
        result = await run_in_threadpool(resend.Emails.send, params)
        return str(result["id"])


def get_email_sender() -> EmailSender:
    if settings.email_provider == "resend":
        if not settings.resend_api_key:
            raise RuntimeError("EMAIL_PROVIDER=resend requires RESEND_API_KEY")
        return ResendSender(settings.resend_api_key)
    return SMTPSender()

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.core.config import settings
from app.db.enums import EmailKind
from app.db.models import Lead

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    # Lead fields are untrusted input: HTML templates autoescape, text templates don't need to.
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


_SUBJECTS = {
    EmailKind.PROSPECT_CONFIRMATION: "We received your information",
    EmailKind.ATTORNEY_NOTIFICATION: "New lead: {first} {last}",
}


def render(kind: EmailKind, lead: Lead) -> RenderedEmail:
    name = kind.value.lower()
    ctx = {
        "lead": lead,
        "lead_url": f"{settings.web_base_url.rstrip('/')}/leads/{lead.id}",
        "resume_size_kb": max(1, round(lead.resume_size / 1024)),
        "submitted_at": lead.created_at.strftime("%Y-%m-%d %H:%M UTC"),
    }
    # Header injection is impossible via names: they're stripped/validated, and EmailMessage
    # rejects CR/LF in header values anyway.
    subject = _SUBJECTS[kind].format(first=lead.first_name, last=lead.last_name)
    return RenderedEmail(
        subject=subject,
        html=_env.get_template(f"{name}.html").render(ctx),
        text=_env.get_template(f"{name}.txt").render(ctx),
    )

"""Idempotent local-dev seeding: `python -m app.seed`.

Creates attorney@example.com plus a User row for every ATTORNEY_EMAILS address, all with
SEED_PASSWORD. Existing users are left untouched. Skipped entirely when SEED_PASSWORD is unset.
"""

import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.security import hash_password
from app.db.enums import UserRole
from app.db.models import User, _uuid
from app.db.session import SessionLocal, engine

log = logging.getLogger("app.seed")

DEMO_ATTORNEY = "attorney@example.com"


def _display_name(email: str) -> str:
    local = email.split("@", 1)[0]
    return " ".join(part.capitalize() for part in local.replace("_", ".").split(".") if part) or email


async def seed() -> None:
    if not settings.seed_password:
        log.info("SEED_PASSWORD not set; skipping seed")
        return
    emails = list(dict.fromkeys(e.lower() for e in [DEMO_ATTORNEY, *settings.attorney_emails]))
    password_hash = hash_password(settings.seed_password)
    async with SessionLocal() as session, session.begin():
        for email in emails:
            await session.execute(
                insert(User)
                .values(
                    id=_uuid(),
                    email=email,
                    password_hash=password_hash,
                    name=_display_name(email),
                    role=UserRole.ATTORNEY,
                )
                .on_conflict_do_nothing(index_elements=[User.email])
            )
    log.info("Seeded attorney accounts: %s", ", ".join(emails))
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(seed())

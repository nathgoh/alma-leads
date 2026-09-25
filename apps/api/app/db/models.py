"""SQLAlchemy mappings of the tables Prisma's migrations create.

Mirrors prisma/schema.prisma; drift-checked by tests/test_schema_drift.py. Mapping rules
(see docs/system-design.md §5): Prisma-client-side defaults (@default(uuid()), @updatedAt)
are supplied here in Python; DB-side defaults use server_default; enum types and index names
match what Prisma generates; SQLAlchemy never creates types or tables.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import ENUM, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.enums import EmailKind, EmailStatus, LeadState, UserRole


def _uuid() -> str:
    return str(uuid4())


def _pg_enum(enum_cls: type) -> ENUM:
    # Prisma creates the type; SQLAlchemy must never CREATE/DROP it.
    return ENUM(enum_cls, name=enum_cls.__name__, create_type=False)


class Base(DeclarativeBase):
    type_annotation_map = {str: Text, datetime: TIMESTAMP(precision=3), int: Integer}


class User(Base):
    __tablename__ = "User"
    __table_args__ = (Index("User_email_key", "email", unique=True),)

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str]
    password_hash: Mapped[str] = mapped_column("passwordHash")
    name: Mapped[str]
    role: Mapped[UserRole] = mapped_column(
        _pg_enum(UserRole), default=UserRole.ATTORNEY, server_default=UserRole.ATTORNEY.value
    )
    created_at: Mapped[datetime] = mapped_column("createdAt", server_default=func.now())


class Lead(Base):
    __tablename__ = "Lead"
    __table_args__ = (
        Index("Lead_state_createdAt_idx", "state", "createdAt"),
        Index("Lead_createdAt_idx", "createdAt"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    first_name: Mapped[str] = mapped_column("firstName")
    last_name: Mapped[str] = mapped_column("lastName")
    email: Mapped[str]
    state: Mapped[LeadState] = mapped_column(
        _pg_enum(LeadState), default=LeadState.PENDING, server_default=LeadState.PENDING.value
    )
    resume_key: Mapped[str] = mapped_column("resumeKey")
    resume_name: Mapped[str] = mapped_column("resumeName")
    resume_size: Mapped[int] = mapped_column("resumeSize")
    resume_mime: Mapped[str] = mapped_column("resumeMime")
    created_at: Mapped[datetime] = mapped_column("createdAt", server_default=func.now())
    # @updatedAt is maintained by the Prisma *client*, so there is no DB default or trigger.
    updated_at: Mapped[datetime] = mapped_column("updatedAt", default=func.now(), onupdate=func.now())
    reached_out_at: Mapped[datetime | None] = mapped_column("reachedOutAt")
    reached_out_by: Mapped[str | None] = mapped_column(
        "reachedOutBy", ForeignKey("User.id", ondelete="SET NULL", onupdate="CASCADE")
    )

    reached_out_user: Mapped[User | None] = relationship(lazy="raise")
    emails: Mapped[list["EmailLog"]] = relationship(
        back_populates="lead", lazy="raise", order_by="EmailLog.created_at"
    )


class EmailLog(Base):
    __tablename__ = "EmailLog"
    __table_args__ = (
        Index("EmailLog_leadId_idx", "leadId"),
        Index("EmailLog_status_idx", "status"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    lead_id: Mapped[str] = mapped_column(
        "leadId", ForeignKey("Lead.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    kind: Mapped[EmailKind] = mapped_column(_pg_enum(EmailKind))
    recipient: Mapped[str]
    status: Mapped[EmailStatus] = mapped_column(
        _pg_enum(EmailStatus), default=EmailStatus.PENDING, server_default=EmailStatus.PENDING.value
    )
    provider_id: Mapped[str | None] = mapped_column("providerId")
    error: Mapped[str | None]
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    sent_at: Mapped[datetime | None] = mapped_column("sentAt")
    created_at: Mapped[datetime] = mapped_column("createdAt", server_default=func.now())

    lead: Mapped[Lead] = relationship(back_populates="emails", lazy="raise")

import enum


class LeadState(enum.StrEnum):
    PENDING = "PENDING"
    REACHED_OUT = "REACHED_OUT"


class UserRole(enum.StrEnum):
    ATTORNEY = "ATTORNEY"
    ADMIN = "ADMIN"


class EmailKind(enum.StrEnum):
    PROSPECT_CONFIRMATION = "PROSPECT_CONFIRMATION"
    ATTORNEY_NOTIFICATION = "ATTORNEY_NOTIFICATION"


class EmailStatus(enum.StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Keyed on request.client.host. uvicorn --proxy-headers + FORWARDED_ALLOW_IPS makes that the
# real client IP when the hop is the trusted NextJS proxy, and the peer address otherwise.
# In-process storage: swap for a Redis storage_uri once there is more than one API replica.
limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)


def leads_limit() -> str:
    return settings.rate_limit_leads


def login_limit() -> str:
    return settings.rate_limit_login

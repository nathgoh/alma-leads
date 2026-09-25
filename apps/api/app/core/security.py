from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pwdlib import PasswordHash
from starlette.middleware.base import RequestResponseEndpoint

from app.core.config import settings

password_hash = PasswordHash.recommended()  # Argon2id

# Verified against when the email is unknown, so login timing doesn't reveal which accounts exist.
_DUMMY_HASH = password_hash.hash("dummy-password-for-timing")

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        password_hash.verify(password, _DUMMY_HASH)
        return False
    return password_hash.verify(password, hashed)


def create_access_token(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(seconds=settings.jwt_ttl_seconds)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Return the user id, or None if the token is invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp"]}
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.jwt_ttl_seconds,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    # Same name/path/attributes as set_session_cookie, or the browser keeps the old cookie.
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def enforce_same_origin(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """CSRF control: every unsafe request must come from an allowed origin.

    Origin is *required* (browsers always send it on non-GET/HEAD fetches), and
    Sec-Fetch-Site, when present, must be `same-origin`.
    """
    if request.method in UNSAFE_METHODS:
        fetch_site = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")
        if (fetch_site is not None and fetch_site != "same-origin") or origin not in settings.allowed_origins:
            return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
    return await call_next(request)

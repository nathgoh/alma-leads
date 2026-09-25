from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.enums import UserRole
from app.db.models import User
from app.db.session import get_session

_UNAUTHENTICATED = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


async def get_current_attorney(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    user_id = decode_access_token(token) if token else None
    if user_id is None:
        raise _UNAUTHENTICATED
    async with session.begin():
        user = await session.get(User, user_id)
    if user is None:
        raise _UNAUTHENTICATED
    if user.role not in (UserRole.ATTORNEY, UserRole.ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    return user


CurrentAttorney = Annotated[User, Depends(get_current_attorney)]

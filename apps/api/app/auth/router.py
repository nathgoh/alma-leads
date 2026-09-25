from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentAttorney
from app.core.http import require_json
from app.core.rate_limit import limiter, login_limit
from app.core.security import (
    clear_session_cookie,
    create_access_token,
    set_session_cookie,
    verify_password,
)
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import LoginRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(require_json)])
@limiter.limit(login_limit)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserOut:
    async with session.begin():
        user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    set_session_cookie(response, create_access_token(user.id))
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_session_cookie(response)


@router.get("/me")
async def me(user: CurrentAttorney) -> UserOut:
    return UserOut.model_validate(user)

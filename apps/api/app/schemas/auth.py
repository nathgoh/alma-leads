from pydantic import EmailStr, Field

from app.db.enums import UserRole
from app.schemas.base import ApiModel


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(ApiModel):
    id: str
    email: str
    name: str
    role: UserRole

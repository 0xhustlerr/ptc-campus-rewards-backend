from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole, UserStatus, VendorType
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class UserRead(ORMModel):
    id: UUID
    email: str
    phone: str | None
    role: UserRole
    status: UserStatus


class RegisterUserRequest(BaseModel):
    """Admin-created user account (closed-loop campus system)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    phone: str | None = None
    # Student fields
    student_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    cohort: str | None = None
    program: str | None = None
    # Vendor fields
    vendor_name: str | None = None
    vendor_type: VendorType | None = None

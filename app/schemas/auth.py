from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

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


class SelfRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    phone: str | None = None
    student_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    cohort: str | None = None
    program: str | None = None
    vendor_name: str | None = None
    vendor_type: VendorType | None = None

    @model_validator(mode="after")
    def validate_role_fields(self) -> "SelfRegisterRequest":
        if self.role == UserRole.student and not all(
            [self.student_number, self.first_name, self.last_name]
        ):
            raise ValueError(
                "student_number, first_name, and last_name are required for student registration"
            )
        if self.role == UserRole.vendor and not all([self.vendor_name, self.vendor_type]):
            raise ValueError("vendor_name and vendor_type are required for vendor registration")
        return self

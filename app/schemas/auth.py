from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import UserRole, UserStatus, VendorType
from app.schemas.admin import (
    PendingStaffProfileRead,
    PendingStudentProfileRead,
    PendingVendorProfileRead,
)
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def new_must_differ(self) -> "ChangePasswordRequest":
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from current password")
        return self


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
    student_profile: PendingStudentProfileRead | None = None
    staff_profile: PendingStaffProfileRead | None = None
    vendor_profile: PendingVendorProfileRead | None = None


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
    # Staff fields (shared first/last name with student)
    department: str | None = None


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
    department: str | None = None

    @model_validator(mode="after")
    def validate_role_fields(self) -> "SelfRegisterRequest":
        if self.role == UserRole.student and not all(
            [self.student_number, self.first_name, self.last_name]
        ):
            raise ValueError(
                "student_number, first_name, and last_name are required for student registration"
            )
        if self.role == UserRole.staff and not all([self.first_name, self.last_name]):
            raise ValueError("first_name and last_name are required for staff registration")
        if self.role == UserRole.vendor and not all([self.vendor_name, self.vendor_type]):
            raise ValueError("vendor_name and vendor_type are required for vendor registration")
        return self

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.enums import UserRole, UserStatus, VendorType, WalletStatus
from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict | None = None
    after: dict | None = None
    created_at: datetime


class WalletStatusUpdate(BaseModel):
    status: WalletStatus


class PendingStudentProfileRead(ORMModel):
    student_number: str
    first_name: str
    last_name: str
    cohort: str | None = None
    program: str | None = None


class PendingVendorProfileRead(ORMModel):
    name: str
    vendor_type: VendorType


class PendingStaffProfileRead(ORMModel):
    first_name: str
    last_name: str
    department: str | None = None


class PendingRegistrationRead(ORMModel):
    id: UUID
    email: str
    phone: str | None
    role: UserRole
    status: UserStatus
    created_at: datetime
    student_profile: PendingStudentProfileRead | None = None
    staff_profile: PendingStaffProfileRead | None = None
    vendor_profile: PendingVendorProfileRead | None = None


class AdminUserStatusUpdate(BaseModel):
    status: UserStatus
    student_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    cohort: str | None = None
    program: str | None = None
    department: str | None = None
    vendor_name: str | None = None
    vendor_type: VendorType | None = None

    @model_validator(mode="after")
    def validate_profile_fields_on_activate(self) -> "AdminUserStatusUpdate":
        if self.status != UserStatus.active:
            return self
        if any([self.student_number, self.cohort, self.program]) and not all(
            [self.student_number, self.first_name, self.last_name]
        ):
            raise ValueError(
                "student_number, first_name, and last_name must all be provided together"
            )
        if any([self.first_name, self.last_name, self.department]) and not all(
            [self.first_name, self.last_name]
        ):
            raise ValueError("first_name and last_name must all be provided together")
        if any([self.vendor_name, self.vendor_type]) and not all(
            [self.vendor_name, self.vendor_type]
        ):
            raise ValueError("vendor_name and vendor_type must all be provided together")
        return self

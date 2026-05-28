"""Admin-provisioned user registration."""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError
from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus, VendorStatus
from app.models.user import User
from app.models.vendor import Vendor
from app.repositories.user import UserRepository
from app.repositories.vendor import VendorRepository
from app.schemas.auth import RegisterUserRequest
from app.services.audit_service import AuditActions, AuditService
from app.services.student_service import StudentService
from app.services.system_accounts_service import SystemAccountsService


class UserAdminService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def register_user(self, data: RegisterUserRequest, *, created_by: uuid.UUID) -> User:
        if data.role == UserRole.admin:
            raise AppError(
                "Admin accounts cannot be provisioned via the API",
                code="admin_provision_forbidden",
            )
        if self.users.get_by_email(data.email.lower()):
            raise ConflictError("Email already registered")

        user = User(
            email=data.email.lower(),
            phone=data.phone,
            hashed_password=hash_password(data.password),
            role=data.role,
            status=UserStatus.active,
        )
        self.users.create(user)

        if data.role == UserRole.student:
            if not all([data.student_number, data.first_name, data.last_name]):
                raise AppError("Student number, first name, and last name are required")
            StudentService(self.db).create_student(
                email=data.email,
                password=data.password,
                student_number=data.student_number,
                first_name=data.first_name,
                last_name=data.last_name,
                cohort=data.cohort,
                program=data.program,
                phone=data.phone,
                skip_user_creation=True,
                existing_user=user,
            )
        elif data.role == UserRole.vendor:
            if not data.vendor_name or not data.vendor_type:
                raise AppError("Vendor name and type are required")
            vendor = Vendor(
                user_id=user.id,
                name=data.vendor_name,
                vendor_type=data.vendor_type,
                status=VendorStatus.active,
            )
            VendorRepository(self.db).create(vendor)
            SystemAccountsService(self.db).ensure_vendor_account(vendor.id, vendor.name)

        self.audit.record(
            AuditActions.USER_REGISTERED,
            "user",
            actor_user_id=created_by,
            entity_id=str(user.id),
            after={"email": user.email, "role": user.role.value},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(user)
        return user

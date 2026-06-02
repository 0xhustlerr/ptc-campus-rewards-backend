"""Admin-provisioned user registration."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus, VendorStatus, VendorType
from app.models.user import User
from app.models.vendor import Vendor
from app.repositories.student import StudentRepository
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
            self.provision_vendor(user, name=data.vendor_name, vendor_type=data.vendor_type)

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

    def provision_vendor(self, user: User, *, name: str, vendor_type: VendorType) -> Vendor:
        vendor = Vendor(
            user_id=user.id,
            name=name,
            vendor_type=vendor_type,
            status=VendorStatus.active,
        )
        VendorRepository(self.db).create(vendor)
        SystemAccountsService(self.db).ensure_vendor_account(vendor.id, vendor.name)
        return vendor

    def list_users_by_status(self, status: UserStatus) -> list[User]:
        stmt = select(User).where(User.status == status).order_by(User.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def list_pending_registrations(self) -> list[User]:
        stmt = (
            select(User)
            .options(joinedload(User.student), joinedload(User.vendor))
            .where(User.status == UserStatus.pending)
            .order_by(User.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def update_user_status(
        self,
        user_id: uuid.UUID,
        status: UserStatus,
        *,
        actor_id: uuid.UUID,
        student_number: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        cohort: str | None = None,
        program: str | None = None,
        vendor_name: str | None = None,
        vendor_type: VendorType | None = None,
    ) -> User:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        previous = user.status

        if (
            status == UserStatus.active
            and user.role == UserRole.student
            and previous == UserStatus.pending
        ):
            if not StudentRepository(self.db).get_by_user_id(user.id):
                if not all([student_number, first_name, last_name]):
                    raise AppError(
                        "Student profile is required before approval. "
                        "Provide student number, first name, and last name.",
                        code="student_profile_missing",
                    )
                StudentService(self.db).create_student(
                    email=user.email,
                    password="",
                    student_number=student_number,
                    first_name=first_name,
                    last_name=last_name,
                    cohort=cohort,
                    program=program,
                    phone=user.phone,
                    skip_user_creation=True,
                    existing_user=user,
                )

        if (
            status == UserStatus.active
            and user.role == UserRole.vendor
            and previous == UserStatus.pending
        ):
            if not VendorRepository(self.db).get_by_user_id(user.id):
                if not vendor_name or not vendor_type:
                    raise AppError(
                        "Vendor profile is required before approval. "
                        "Provide business name and vendor type.",
                        code="vendor_profile_missing",
                    )
                self.provision_vendor(user, name=vendor_name, vendor_type=vendor_type)

        user.status = status
        action = AuditActions.USER_STATUS_CHANGED
        if previous == UserStatus.pending and status == UserStatus.active:
            action = AuditActions.USER_APPROVED
        elif previous == UserStatus.pending and status == UserStatus.suspended:
            action = AuditActions.USER_REJECTED
        self.audit.record(
            action,
            "user",
            actor_user_id=actor_id,
            entity_id=str(user.id),
            before={"status": previous.value},
            after={"status": status.value},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(user)
        return user

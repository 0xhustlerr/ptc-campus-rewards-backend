"""Staff registration and profile."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.models.enums import StaffStatus, UserRole, UserStatus
from app.models.staff import Staff
from app.models.user import User
from app.repositories.staff import StaffRepository
from app.repositories.user import UserRepository


class StaffService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.staff = StaffRepository(db)
        self.users = UserRepository(db)

    def create_staff(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        department: str | None = None,
        phone: str | None = None,
        skip_user_creation: bool = False,
        existing_user: User | None = None,
    ) -> Staff:
        user = existing_user or User(
            email=email.lower(),
            phone=phone,
            hashed_password=hash_password(password),
            role=UserRole.staff,
            status=UserStatus.active,
        )
        if not skip_user_creation:
            self.users.create(user)

        staff = Staff(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            department=department,
            status=StaffStatus.active,
        )
        self.staff.create(staff)
        self.db.flush()
        self.db.expire(staff)
        loaded = self.staff.get_by_user_id(user.id)
        if not loaded:
            raise NotFoundError("Staff not found after creation")
        return loaded

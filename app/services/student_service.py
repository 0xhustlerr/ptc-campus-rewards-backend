"""Student registration and profile."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.enums import StudentStatus, UserRole, UserStatus
from app.models.student import Student
from app.models.user import User
from app.repositories.student import StudentRepository
from app.repositories.user import UserRepository
from app.services.wallet_service import WalletService


class StudentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.students = StudentRepository(db)
        self.users = UserRepository(db)
        self.wallets = WalletService(db)

    def create_student(
        self,
        *,
        email: str,
        password: str,
        student_number: str,
        first_name: str,
        last_name: str,
        cohort: str | None = None,
        program: str | None = None,
        phone: str | None = None,
        skip_user_creation: bool = False,
        existing_user: User | None = None,
    ) -> Student:
        if not skip_user_creation:
            if self.users.get_by_email(email.lower()):
                raise ConflictError("Email already registered")
        if self.students.get_by_student_number(student_number):
            raise ConflictError("Student number already exists")

        user = existing_user or User(
            email=email.lower(),
            phone=phone,
            hashed_password=hash_password(password),
            role=UserRole.student,
            status=UserStatus.active,
        )
        if not skip_user_creation:
            self.users.create(user)

        student = Student(
            user_id=user.id,
            student_number=student_number,
            first_name=first_name,
            last_name=last_name,
            cohort=cohort,
            program=program,
            status=StudentStatus.active,
        )
        self.students.create(student)
        self.wallets.create_wallet_for_student(student.id)
        self.db.flush()
        self.db.expire(student)
        loaded = self.students.get_by_id(student.id)
        if not loaded:
            raise NotFoundError("Student not found after creation")
        return loaded

    def get_by_id(self, student_id: UUID) -> Student:
        student = self.students.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student not found")
        return student

    def get_by_user_id(self, user_id: UUID) -> Student:
        student = self.students.get_by_user_id(user_id)
        if not student:
            raise NotFoundError("Student not found")
        return student

    def list_students(self) -> list[Student]:
        return self.students.list_all()

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.student import Student
from app.models.user import User


class StudentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, student_id: uuid.UUID) -> Student | None:
        stmt = (
            select(Student)
            .options(joinedload(Student.user), joinedload(Student.wallet))
            .where(Student.id == student_id)
        )
        return self.db.scalars(stmt).first()

    def get_by_user_id(self, user_id: uuid.UUID) -> Student | None:
        stmt = (
            select(Student)
            .options(joinedload(Student.user), joinedload(Student.wallet))
            .where(Student.user_id == user_id)
        )
        return self.db.scalars(stmt).first()

    def get_by_student_number(self, student_number: str) -> Student | None:
        stmt = select(Student).where(Student.student_number == student_number)
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[Student]:
        stmt = select(Student).options(joinedload(Student.user), joinedload(Student.wallet))
        return list(self.db.scalars(stmt).all())

    def create(self, student: Student) -> Student:
        self.db.add(student)
        self.db.flush()
        return student

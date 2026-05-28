import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.scalars(stmt).first()

    def list_by_role(self, role: UserRole | None = None) -> list[User]:
        stmt = select(User)
        if role:
            stmt = stmt.where(User.role == role)
        return list(self.db.scalars(stmt).all())

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

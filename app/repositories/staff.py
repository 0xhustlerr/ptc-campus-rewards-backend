import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.staff import Staff
from app.models.user import User


class StaffRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: uuid.UUID) -> Staff | None:
        stmt = (
            select(Staff)
            .options(joinedload(Staff.user))
            .where(Staff.user_id == user_id)
        )
        return self.db.scalars(stmt).first()

    def create(self, staff: Staff) -> Staff:
        self.db.add(staff)
        self.db.flush()
        return staff

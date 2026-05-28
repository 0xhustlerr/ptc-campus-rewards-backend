import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.student import Student
from app.models.wallet import Wallet


class WalletRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, wallet_id: uuid.UUID) -> Wallet | None:
        stmt = (
            select(Wallet)
            .options(joinedload(Wallet.student).joinedload(Student.user))
            .where(Wallet.id == wallet_id)
        )
        return self.db.scalars(stmt).first()

    def get_by_student_id(self, student_id: uuid.UUID) -> Wallet | None:
        stmt = (
            select(Wallet)
            .options(joinedload(Wallet.student).joinedload(Student.user))
            .where(Wallet.student_id == student_id)
        )
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[Wallet]:
        stmt = select(Wallet).options(joinedload(Wallet.student))
        return list(self.db.scalars(stmt).all())

    def create(self, wallet: Wallet) -> Wallet:
        self.db.add(wallet)
        self.db.flush()
        return wallet

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import RedemptionStatus
from app.models.redemption import Redemption


class RedemptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_idempotency_key(self, key: str) -> Redemption | None:
        stmt = (
            select(Redemption)
            .options(
                joinedload(Redemption.student),
                joinedload(Redemption.reward_item),
                joinedload(Redemption.vendor),
            )
            .where(Redemption.idempotency_key == key)
        )
        return self.db.scalars(stmt).first()

    def create(self, redemption: Redemption) -> Redemption:
        self.db.add(redemption)
        self.db.flush()
        return redemption

    def list_by_vendor(self, vendor_id: uuid.UUID, limit: int = 100) -> list[Redemption]:
        stmt = (
            select(Redemption)
            .options(
                joinedload(Redemption.student),
                joinedload(Redemption.reward_item),
                joinedload(Redemption.vendor),
            )
            .where(Redemption.vendor_id == vendor_id)
            .order_by(Redemption.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_all(self, limit: int = 200) -> list[Redemption]:
        stmt = (
            select(Redemption)
            .options(joinedload(Redemption.student), joinedload(Redemption.reward_item))
            .order_by(Redemption.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

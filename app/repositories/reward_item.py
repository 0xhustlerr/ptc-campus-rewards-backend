import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.reward_item import RewardItem


class RewardItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: uuid.UUID) -> RewardItem | None:
        return self.db.get(RewardItem, item_id)

    def list_active(self) -> list[RewardItem]:
        stmt = select(RewardItem).where(RewardItem.active.is_(True))
        return list(self.db.scalars(stmt).all())

    def list_all(self) -> list[RewardItem]:
        return list(self.db.scalars(select(RewardItem)).all())

    def create(self, item: RewardItem) -> RewardItem:
        self.db.add(item)
        self.db.flush()
        return item

    def reserve_inventory(self, item_id: uuid.UUID) -> bool:
        """Atomically decrement inventory when tracked; always succeeds when unlimited."""
        item = self.get_by_id(item_id)
        if item is None:
            return False
        if item.inventory_count is None:
            return True
        result = self.db.execute(
            update(RewardItem)
            .where(
                RewardItem.id == item_id,
                RewardItem.inventory_count > 0,
            )
            .values(inventory_count=RewardItem.inventory_count - 1)
        )
        return result.rowcount == 1

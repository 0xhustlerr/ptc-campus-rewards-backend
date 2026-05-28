"""Catalog items redeemable with PTC Credits."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RewardCategory


class RewardItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reward_items"

    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[RewardCategory] = mapped_column(
        Enum(RewardCategory, name="reward_category"),
        nullable=False,
    )
    price_tokens: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    inventory_count: Mapped[int | None] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    vendor: Mapped["Vendor | None"] = relationship("Vendor", back_populates="reward_items")
    redemptions: Mapped[list["Redemption"]] = relationship("Redemption", back_populates="reward_item")

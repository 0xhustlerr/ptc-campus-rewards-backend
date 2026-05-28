"""Vendor profile for food truck, school store, campus perks."""

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import VendorStatus, VendorType


class Vendor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "vendors"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor_type: Mapped[VendorType] = mapped_column(
        Enum(VendorType, name="vendor_type"),
        nullable=False,
    )
    status: Mapped[VendorStatus] = mapped_column(
        Enum(VendorStatus, name="vendor_status"),
        nullable=False,
        default=VendorStatus.active,
    )

    user: Mapped["User"] = relationship("User", back_populates="vendor")
    ledger_accounts: Mapped[list["LedgerAccount"]] = relationship(
        "LedgerAccount",
        back_populates="vendor",
    )
    reward_items: Mapped[list["RewardItem"]] = relationship("RewardItem", back_populates="vendor")
    redemptions: Mapped[list["Redemption"]] = relationship("Redemption", back_populates="vendor")

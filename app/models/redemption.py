"""Vendor redemption records."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import RedemptionStatus


class Redemption(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "redemptions"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reward_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reward_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_tokens: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[RedemptionStatus] = mapped_column(
        Enum(RedemptionStatus, name="redemption_status"),
        nullable=False,
        default=RedemptionStatus.pending,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    balance_before: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    ledger_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ledger_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    student: Mapped["Student"] = relationship("Student", back_populates="redemptions")
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="redemptions")
    reward_item: Mapped["RewardItem"] = relationship("RewardItem", back_populates="redemptions")
    ledger_transaction: Mapped["LedgerTransaction | None"] = relationship(
        "LedgerTransaction",
        back_populates="redemptions",
    )

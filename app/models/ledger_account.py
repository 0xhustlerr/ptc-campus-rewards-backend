"""Ledger accounts — student wallets, rewards pool, vendor revenue, adjustments."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import AccountType


class LedgerAccount(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ledger_accounts"

    wallet_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    wallet: Mapped["Wallet | None"] = relationship("Wallet", back_populates="ledger_accounts")
    vendor: Mapped["Vendor | None"] = relationship("Vendor", back_populates="ledger_accounts")
    entries: Mapped[list["LedgerEntry"]] = relationship("LedgerEntry", back_populates="account")

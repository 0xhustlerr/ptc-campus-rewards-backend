"""Student PTC Credits wallet — balance derived from ledger entries only."""

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import WalletStatus

DEFAULT_CURRENCY = "PTC"


class Wallet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "wallets"

    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    currency_code: Mapped[str] = mapped_column(String(8), nullable=False, default=DEFAULT_CURRENCY)
    status: Mapped[WalletStatus] = mapped_column(
        Enum(WalletStatus, name="wallet_status"),
        nullable=False,
        default=WalletStatus.active,
    )

    student: Mapped["Student"] = relationship("Student", back_populates="wallet")
    ledger_accounts: Mapped[list["LedgerAccount"]] = relationship(
        "LedgerAccount",
        back_populates="wallet",
    )

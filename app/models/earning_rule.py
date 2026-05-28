"""Rules for issuing PTC Credits."""

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EarningRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "earning_rules"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        doc="PTC Credits awarded per event",
    )
    daily_limit: Mapped[int | None] = mapped_column(nullable=True)
    weekly_limit: Mapped[int | None] = mapped_column(nullable=True)
    requires_note: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    earning_events: Mapped[list["EarningEvent"]] = relationship(
        "EarningEvent",
        back_populates="rule",
    )

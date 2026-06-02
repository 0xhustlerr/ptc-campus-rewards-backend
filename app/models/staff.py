"""Staff profile linked to a user account."""

import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import StaffStatus


class Staff(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "staff"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[StaffStatus] = mapped_column(
        Enum(StaffStatus, name="staff_status"),
        nullable=False,
        default=StaffStatus.active,
    )

    user: Mapped["User"] = relationship("User", back_populates="staff")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

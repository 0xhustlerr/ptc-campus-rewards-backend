"""Student profile linked to a user account."""

import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import StudentStatus


class Student(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "students"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    student_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    cohort: Mapped[str | None] = mapped_column(String(64), nullable=True)
    program: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, name="student_status"),
        nullable=False,
        default=StudentStatus.active,
    )

    user: Mapped["User"] = relationship("User", back_populates="student")
    wallet: Mapped["Wallet | None"] = relationship("Wallet", back_populates="student", uselist=False)
    earning_events: Mapped[list["EarningEvent"]] = relationship("EarningEvent", back_populates="student")
    redemptions: Mapped[list["Redemption"]] = relationship("Redemption", back_populates="student")
    qr_sessions: Mapped[list["QRSession"]] = relationship("QRSession", back_populates="student")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

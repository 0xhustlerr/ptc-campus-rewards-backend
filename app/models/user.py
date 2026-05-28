"""User accounts — authentication and role."""

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole, UserStatus


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        nullable=False,
        default=UserStatus.active,
    )

    student: Mapped["Student | None"] = relationship("Student", back_populates="user", uselist=False)
    vendor: Mapped["Vendor | None"] = relationship("Vendor", back_populates="user", uselist=False)
    refresh_tokens: Mapped[list["OAuthRefreshToken"]] = relationship(
        "OAuthRefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

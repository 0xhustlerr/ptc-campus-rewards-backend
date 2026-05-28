"""Stored admin metrics snapshots from Celery jobs."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class AdminMetricsSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "admin_metrics_snapshots"

    snapshot_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_json: Mapped[dict[str, Any]] = mapped_column("data", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

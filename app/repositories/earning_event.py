import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.earning_event import EarningEvent
from app.models.enums import EarningEventStatus


def _campus_day_start_utc() -> datetime:
    """Start of 'today' in the configured campus timezone, expressed in UTC."""
    try:
        tz = ZoneInfo(get_settings().campus_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        tz = UTC
    local_midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(UTC)


class EarningEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, event: EarningEvent) -> EarningEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def get_by_id(self, event_id: uuid.UUID) -> EarningEvent | None:
        return self.db.get(EarningEvent, event_id)

    def get_by_idempotency_key(self, key: str) -> EarningEvent | None:
        stmt = select(EarningEvent).where(EarningEvent.idempotency_key == key)
        return self.db.scalars(stmt).first()

    def get_for_update(self, event_id: uuid.UUID) -> EarningEvent | None:
        """Lock a single event row to serialize approve/reject transitions."""
        stmt = select(EarningEvent).where(EarningEvent.id == event_id).with_for_update()
        return self.db.scalars(stmt).first()

    def list_pending(self) -> list[EarningEvent]:
        stmt = (
            select(EarningEvent)
            .options(joinedload(EarningEvent.student), joinedload(EarningEvent.rule))
            .where(EarningEvent.status == EarningEventStatus.pending)
            .order_by(EarningEvent.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def count_rule_usage(
        self,
        student_id: uuid.UUID,
        rule_id: uuid.UUID,
        *,
        since: datetime,
    ) -> int:
        stmt = select(func.count()).select_from(EarningEvent).where(
            EarningEvent.student_id == student_id,
            EarningEvent.rule_id == rule_id,
            EarningEvent.created_at >= since,
            EarningEvent.status.in_(
                [EarningEventStatus.posted, EarningEventStatus.approved, EarningEventStatus.pending]
            ),
        )
        return int(self.db.scalar(stmt) or 0)

    def daily_count(self, student_id: uuid.UUID, rule_id: uuid.UUID) -> int:
        since = _campus_day_start_utc()
        return self.count_rule_usage(student_id, rule_id, since=since)

    def weekly_count(self, student_id: uuid.UUID, rule_id: uuid.UUID) -> int:
        since = datetime.now(UTC) - timedelta(days=7)
        return self.count_rule_usage(student_id, rule_id, since=since)

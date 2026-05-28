import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.earning_event import EarningEvent
from app.models.enums import EarningEventStatus


class EarningEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, event: EarningEvent) -> EarningEvent:
        self.db.add(event)
        self.db.flush()
        return event

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
        since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.count_rule_usage(student_id, rule_id, since=since)

    def weekly_count(self, student_id: uuid.UUID, rule_id: uuid.UUID) -> int:
        since = datetime.now(UTC) - timedelta(days=7)
        return self.count_rule_usage(student_id, rule_id, since=since)

"""Staff issue PTC Credits via earning rules."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.earning_event import EarningEvent
from app.models.enums import EarningEventStatus
from app.repositories.earning_event import EarningEventRepository
from app.repositories.earning_rule import EarningRuleRepository
from app.repositories.student import StudentRepository
from app.services.audit_service import AuditActions, AuditService
from app.services.ledger_service import LedgerService


class EarningService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.students = StudentRepository(db)
        self.rules = EarningRuleRepository(db)
        self.events = EarningEventRepository(db)
        self.ledger = LedgerService(db)
        self.audit = AuditService(db)

    def issue_reward(
        self,
        *,
        student_id: UUID,
        earning_rule_id: UUID,
        notes: str | None,
        idempotency_key: str,
        issued_by: UUID,
    ) -> EarningEvent:
        existing_tx = self.ledger.get_by_idempotency_key(idempotency_key)
        if existing_tx:
            from sqlalchemy import select

            event = self.db.scalars(
                select(EarningEvent).where(EarningEvent.ledger_transaction_id == existing_tx.id)
            ).first()
            if event:
                return event

        student = self.students.get_by_id(student_id)
        rule = self.rules.get_by_id(earning_rule_id)
        if not student or not student.wallet:
            raise NotFoundError("Student or wallet not found")
        if not rule or not rule.active:
            raise NotFoundError("Earning rule not found or inactive")
        if rule.requires_note and not (notes and notes.strip()):
            raise AppError("Note required for this earning rule", code="note_required")

        if rule.daily_limit is not None:
            if self.events.daily_count(student_id, earning_rule_id) >= rule.daily_limit:
                raise AppError("Daily limit reached for this earning rule", code="daily_limit")
        if rule.weekly_limit is not None:
            if self.events.weekly_count(student_id, earning_rule_id) >= rule.weekly_limit:
                raise AppError("Weekly limit reached for this earning rule", code="weekly_limit")

        amount = Decimal(rule.token_amount)
        status = EarningEventStatus.pending if rule.requires_approval else EarningEventStatus.posted

        event = EarningEvent(
            student_id=student_id,
            rule_id=earning_rule_id,
            amount=amount,
            notes=notes,
            status=status,
            issued_by=issued_by,
        )
        self.events.create(event)

        if status == EarningEventStatus.posted:
            tx = self.ledger.earn(
                wallet_id=student.wallet.id,
                amount=amount,
                idempotency_key=idempotency_key,
                created_by=issued_by,
                reference_type="earning_event",
                reference_id=str(event.id),
                metadata={"rule_code": rule.code, "notes": notes},
            )
            event.ledger_transaction_id = tx.id
            event.status = EarningEventStatus.posted

        if event.status == EarningEventStatus.posted:
            self.audit.record(
                AuditActions.REWARD_ISSUED,
                "earning_event",
                actor_user_id=issued_by,
                entity_id=str(event.id),
                after={
                    "student_id": str(student_id),
                    "rule_id": str(earning_rule_id),
                    "amount": str(amount),
                },
                commit=False,
            )
        self.db.commit()
        self.db.refresh(event)
        return event

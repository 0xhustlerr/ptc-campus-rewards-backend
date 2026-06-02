"""Map ORM models to API schemas."""

from decimal import Decimal

from app.models.earning_event import EarningEvent
from app.models.earning_rule import EarningRule
from app.models.enums import EntryDirection, TransactionStatus
from app.models.ledger import LedgerEntry, LedgerTransaction
from app.models.redemption import Redemption
from app.models.reward_item import RewardItem
from app.models.student import Student
from app.models.user import User
from app.models.wallet import Wallet
from app.models.audit_log import AuditLog
from app.schemas.admin import (
    AuditLogRead,
    PendingRegistrationRead,
    PendingStudentProfileRead,
    PendingVendorProfileRead,
)
from app.schemas.auth import UserRead
from app.schemas.earning_rule import EarningRuleRead
from app.schemas.ledger import LedgerEntryRead, LedgerTransactionRead
from app.schemas.reward import RedemptionRead, RewardItemRead
from app.schemas.student import StudentListItem, StudentRead
from app.schemas.wallet import WalletRead


def user_to_read(user: User) -> UserRead:
    return UserRead.model_validate(user)


def pending_registration_to_read(user: User) -> PendingRegistrationRead:
    student_profile = None
    if user.student:
        student_profile = PendingStudentProfileRead(
            student_number=user.student.student_number,
            first_name=user.student.first_name,
            last_name=user.student.last_name,
            cohort=user.student.cohort,
            program=user.student.program,
        )
    vendor_profile = None
    if user.vendor:
        vendor_profile = PendingVendorProfileRead(
            name=user.vendor.name,
            vendor_type=user.vendor.vendor_type,
        )
    return PendingRegistrationRead(
        id=user.id,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        student_profile=student_profile,
        vendor_profile=vendor_profile,
    )


def audit_log_to_read(log: AuditLog) -> AuditLogRead:
    return AuditLogRead(
        id=log.id,
        actor_user_id=log.actor_user_id,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        before=log.before_json,
        after=log.after_json,
        created_at=log.created_at,
    )


def student_to_read(student: Student, balance: Decimal | None = None) -> StudentRead:
    return StudentRead(
        id=student.id,
        user_id=student.user_id,
        student_number=student.student_number,
        first_name=student.first_name,
        last_name=student.last_name,
        cohort=student.cohort,
        program=student.program,
        status=student.status,
        email=student.user.email if student.user else None,
        wallet_id=student.wallet.id if student.wallet else None,
        balance=balance,
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


def student_to_list_item(student: Student, balance: Decimal | None = None) -> StudentListItem:
    return StudentListItem(
        id=student.id,
        student_number=student.student_number,
        first_name=student.first_name,
        last_name=student.last_name,
        cohort=student.cohort,
        program=student.program,
        status=student.status,
        wallet_id=student.wallet.id if student.wallet else None,
        balance=balance,
    )


def wallet_to_read(wallet: Wallet) -> WalletRead:
    return WalletRead.model_validate(wallet)


def earning_rule_to_read(rule: EarningRule) -> EarningRuleRead:
    return EarningRuleRead.model_validate(rule)


def reward_item_to_read(item: RewardItem) -> RewardItemRead:
    return RewardItemRead.model_validate(item)


def redemption_to_read(r: Redemption) -> RedemptionRead:
    return RedemptionRead.model_validate(r)


def transaction_to_read(tx: LedgerTransaction) -> LedgerTransactionRead:
    amount = sum(
        e.amount for e in tx.entries if e.direction == EntryDirection.debit
    )
    return LedgerTransactionRead(
        id=tx.id,
        transaction_type=tx.transaction_type,
        status=tx.status,
        reference_type=tx.reference_type,
        reference_id=tx.reference_id,
        idempotency_key=tx.idempotency_key,
        amount=amount,
        created_at=tx.created_at,
        entries=[LedgerEntryRead.model_validate(e) for e in tx.entries],
    )

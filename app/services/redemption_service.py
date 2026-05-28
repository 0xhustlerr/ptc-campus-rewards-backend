"""Vendor QR scan and PTC Credits redemption — closed-loop, single-use sessions."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, ForbiddenError, InsufficientCreditsError, NotFoundError
from app.models.enums import RedemptionStatus, VendorStatus, WalletStatus
from app.models.qr_session import QRSession
from app.models.redemption import Redemption
from app.repositories.qr_session import QRSessionRepository
from app.repositories.redemption import RedemptionRepository
from app.repositories.reward_item import RewardItemRepository
from app.repositories.student import StudentRepository
from app.repositories.vendor import VendorRepository
from app.services.audit_service import AuditActions, AuditService
from app.services.ledger_service import LedgerService

settings = get_settings()


class RedemptionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.students = StudentRepository(db)
        self.vendors = VendorRepository(db)
        self.items = RewardItemRepository(db)
        self.redemptions = RedemptionRepository(db)
        self.sessions = QRSessionRepository(db)
        self.ledger = LedgerService(db)
        self.audit = AuditService(db)

    def create_qr_session(self, student_id: UUID) -> tuple[str, QRSession]:
        student = self.students.get_by_id(student_id)
        if not student or not student.wallet:
            raise NotFoundError("Student wallet not found")
        if student.wallet.status != WalletStatus.active:
            raise AppError("Wallet is not active", code="wallet_inactive")

        plain = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plain.encode()).hexdigest()
        session = QRSession(
            student_id=student_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.qr_session_ttl_seconds),
        )
        self.sessions.create(session)
        self.db.commit()
        return plain, session

    def scan_session(self, qr_session_token: str) -> dict:
        session = self._get_valid_session(qr_session_token, for_update=False)
        if not session:
            return {"session_valid": False, "reason": "invalid_token"}

        student = self.students.get_by_id(session.student_id)
        if not student or not student.wallet:
            return {"session_valid": False, "reason": "wallet_not_found"}

        balance = self.ledger.wallet_balance(student.wallet.id)
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        return {
            "session_valid": True,
            "student_display_name": student.full_name,
            "wallet_status": student.wallet.status.value,
            "balance": balance,
            "expires_at": expires_at.isoformat(),
        }

    def redeem(
        self,
        *,
        vendor_user_id: UUID,
        qr_session_token: str,
        reward_item_id: UUID,
        idempotency_key: str,
    ) -> dict:
        existing = self.redemptions.get_by_idempotency_key(idempotency_key)
        if existing:
            if existing.status == RedemptionStatus.completed:
                return self._receipt_from_redemption(existing)
            raise AppError("Redemption already in progress", code="redemption_in_progress")

        vendor = self.vendors.get_by_user_id(vendor_user_id)
        if not vendor or vendor.status != VendorStatus.active:
            raise NotFoundError("Vendor not found")

        item = self.items.get_by_id(reward_item_id)
        if not item or not item.active:
            raise NotFoundError("Reward item not found")
        self._validate_vendor_item(vendor.id, item)

        if not self.items.reserve_inventory(item.id):
            raise AppError("Item out of stock", code="out_of_stock")

        session = self._get_valid_session(qr_session_token, for_update=True)
        if not session:
            self.db.rollback()
            raise AppError("Invalid or expired QR session", code="invalid_session")

        student = self.students.get_by_id(session.student_id)
        if not student or not student.wallet:
            self.db.rollback()
            raise NotFoundError("Student wallet not found")
        if student.wallet.status != WalletStatus.active:
            self.db.rollback()
            raise AppError("Student wallet is not active", code="wallet_inactive")

        amount = Decimal(item.price_tokens)
        balance_before = self.ledger.wallet_balance(student.wallet.id)

        redemption = Redemption(
            student_id=student.id,
            vendor_id=vendor.id,
            reward_item_id=item.id,
            amount_tokens=amount,
            status=RedemptionStatus.pending,
            idempotency_key=idempotency_key,
        )
        self.redemptions.create(redemption)

        try:
            if not self.sessions.mark_used_atomic(session.id):
                raise AppError("QR session already used", code="session_used")

            tx = self.ledger.redeem(
                wallet_id=student.wallet.id,
                vendor_id=vendor.id,
                amount=amount,
                idempotency_key=idempotency_key,
                created_by=vendor_user_id,
                reference_type="redemption",
                reference_id=str(redemption.id),
                metadata={"item": item.name},
            )
            balance_after = self.ledger.wallet_balance(student.wallet.id)

            redemption.ledger_transaction_id = tx.id
            redemption.status = RedemptionStatus.completed
            redemption.balance_before = balance_before
            redemption.balance_after = balance_after

            self.audit.record(
                AuditActions.REDEMPTION_COMPLETED,
                "redemption",
                actor_user_id=vendor_user_id,
                entity_id=str(redemption.id),
                before={"balance": str(balance_before)},
                after={"balance": str(balance_after), "amount": str(amount)},
                commit=False,
            )
            self.db.commit()
            return self._receipt_from_redemption(redemption, vendor_name=vendor.name)

        except Exception as exc:
            self.db.rollback()
            if isinstance(exc, InsufficientCreditsError):
                raise
            if isinstance(exc, AppError):
                raise
            raise AppError("Redemption failed", code="redemption_failed") from exc

    def list_vendor_receipts(self, vendor_user_id: UUID, limit: int = 100) -> list[dict]:
        vendor = self.vendors.get_by_user_id(vendor_user_id)
        if not vendor:
            return []
        return [
            self._receipt_from_redemption(r, vendor_name=vendor.name)
            for r in self.redemptions.list_by_vendor(vendor.id, limit=limit)
            if r.status == RedemptionStatus.completed
        ]

    def _get_valid_session(self, token: str, *, for_update: bool) -> QRSession | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = (
            self.sessions.get_by_token_hash_for_update(token_hash)
            if for_update
            else self.sessions.get_by_token_hash(token_hash)
        )
        if not session or session.used_at is not None:
            return None
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            return None
        return session

    def _validate_vendor_item(self, vendor_id: UUID, item) -> None:
        if item.vendor_id is not None and item.vendor_id != vendor_id:
            raise ForbiddenError("This reward item belongs to another vendor")

    def _receipt_from_redemption(self, r: Redemption, *, vendor_name: str = "") -> dict:
        name = vendor_name
        if not name and r.vendor:
            name = r.vendor.name
        student_name = r.student.full_name if r.student else ""
        item_name = r.reward_item.name if r.reward_item else ""
        balance_before = r.balance_before if r.balance_before is not None else Decimal("0")
        balance_after = r.balance_after if r.balance_after is not None else Decimal("0")
        return {
            "redemption_id": str(r.id),
            "student_display_name": student_name,
            "item_name": item_name,
            "amount": r.amount_tokens,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "vendor_name": name,
            "redeemed_at": r.created_at.isoformat(),
        }

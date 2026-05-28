"""Admin operations — wallet status, ledger adjustments, audit logs."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import WalletStatus
from app.models.wallet import Wallet
from app.repositories.audit_log import AuditLogRepository
from app.schemas.ledger import AdminAdjustmentRequest, AdminReversalRequest
from app.services.audit_service import AuditActions, AuditService
from app.services.ledger_service import LedgerService
from app.services.wallet_service import WalletService


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallets = WalletService(db)
        self.ledger = LedgerService(db)
        self.audit = AuditService(db)
        self.audit_logs = AuditLogRepository(db)

    def update_wallet_status(
        self, wallet_id: UUID, status: WalletStatus, *, actor_id: UUID
    ) -> Wallet:
        wallet = self.wallets.wallets.get_by_id(wallet_id)
        if not wallet:
            raise NotFoundError("Wallet not found")
        before = wallet.status.value
        wallet.status = status
        action = (
            AuditActions.WALLET_FROZEN
            if status == WalletStatus.frozen
            else AuditActions.WALLET_UNFROZEN
        )
        self.audit.record(
            action,
            "wallet",
            actor_user_id=actor_id,
            entity_id=str(wallet_id),
            before={"status": before},
            after={"status": status.value},
            commit=True,
        )
        self.db.refresh(wallet)
        return wallet

    def apply_adjustment(self, body: AdminAdjustmentRequest, *, actor_id: UUID):
        tx = self.ledger.adjustment(
            wallet_id=body.wallet_id,
            amount=body.amount,
            credit_student=body.credit_student,
            idempotency_key=body.idempotency_key,
            created_by=actor_id,
            metadata={"reason": body.reason},
        )
        self.audit.record(
            AuditActions.ADMIN_ADJUSTMENT,
            "ledger_transaction",
            actor_user_id=actor_id,
            entity_id=str(tx.id),
            after={"amount": str(body.amount), "credit_student": body.credit_student},
            commit=True,
        )
        return tx

    def apply_reversal(self, body: AdminReversalRequest, *, actor_id: UUID):
        tx = self.ledger.reverse_transaction(
            body.ledger_transaction_id,
            idempotency_key=body.idempotency_key,
            created_by=actor_id,
        )
        self.audit.record(
            AuditActions.TRANSACTION_REVERSAL,
            "ledger_transaction",
            actor_user_id=actor_id,
            entity_id=str(tx.id),
            after={"reverses": str(body.ledger_transaction_id)},
            commit=True,
        )
        return tx

    def list_audit_logs(self, limit: int) -> list:
        return self.audit_logs.list_recent(limit)
